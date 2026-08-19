"""Introduces the clients entity, natural keys and soft delete.

Revision ID: a1b2c3d4e5f6
Revises: d419612ba5db
Create Date: 2026-08-17 09:40:00.000000

This migration converts four flat tables inherited from the original Excel
file into a relational model with a common root. The backfill runs in
Python (not SQL) because the natural key requires the same text
normalization used by the ETL and the API: strip accents, collapse
whitespace, and lowercase. Reimplementing it in SQL would open the door to
the three layers deriving different keys for the same person.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from tramex_shared import (
    ENTIDADES,
    calcular_clave_cliente,
    calcular_clave_natural,
    calcular_hash_fila,
    clave_es_debil,
    nombre_canonico,
)

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "d419612ba5db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS_TRAMITE = ("master_tramex", "global_entry", "pasaportes", "canada")

#: Columns from the original Excel file that let you infer the person.
#: Not every table has all of them: Master Tramex has no last name and
#: Pasaportes has no passport number, hence the runtime intersection.
CAMPOS_DE_CLIENTE = (
    "nombre",
    "apellido",
    "correo_electronico",
    "telefono",
    "numero_pasaporte",
)


def _columnas_existentes(conexion, tabla: str) -> set[str]:
    inspector = sa.inspect(conexion)
    return {columna["name"] for columna in inspector.get_columns(tabla)}


def upgrade() -> None:
    conexion = op.get_bind()

    # -- 1. Root entity ---------------------------------------------------
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("apellido", sa.Text(), nullable=True),
        sa.Column("correo_electronico", sa.Text(), nullable=True),
        sa.Column("telefono", sa.Text(), nullable=True),
        sa.Column("numero_pasaporte", sa.Text(), nullable=True),
        sa.Column("clave_natural", sa.Text(), nullable=False),
        sa.Column("hash_fila", sa.Text(), nullable=False),
        sa.Column(
            "cargado_en",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("eliminado_en", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clientes_nombre", "clientes", ["nombre"])
    op.create_index("ix_clientes_correo_electronico", "clientes", ["correo_electronico"])
    op.create_index("ix_clientes_numero_pasaporte", "clientes", ["numero_pasaporte"])
    op.create_index("ix_clientes_eliminado_en", "clientes", ["eliminado_en"])

    # -- 2. New columns, still optional so they can be backfilled ---------
    for tabla in TABLAS_TRAMITE:
        op.add_column(tabla, sa.Column("cliente_id", sa.Integer(), nullable=True))
        op.add_column(tabla, sa.Column("clave_natural", sa.Text(), nullable=True))
        op.add_column(tabla, sa.Column("hash_fila", sa.Text(), nullable=True))
        op.add_column(
            tabla,
            sa.Column(
                "actualizado_en",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.add_column(tabla, sa.Column("eliminado_en", sa.DateTime(), nullable=True))

    # -- 3. Backfill: infer the person behind each row ---------------------
    # Walked in two passes, just like `CRUDCliente.resolver_o_crear`: first
    # the rows carrying a hard identifier (passport or email), which are
    # the ones that define identity, then the ones without it, which only
    # attach to an already-known person if the name is unambiguous.
    filas_por_tabla: dict[str, list[dict]] = {}

    for tabla in TABLAS_TRAMITE:
        columnas = _columnas_existentes(conexion, tabla)
        campos_lectura = sorted(columnas - {"cliente_id", "clave_natural", "hash_fila"})
        seleccion = ", ".join(campos_lectura)
        filas_por_tabla[tabla] = [
            dict(fila)
            for fila in conexion.execute(sa.text(f"SELECT {seleccion} FROM {tabla}"))
            .mappings()
            .all()
        ]

    clientes_por_clave: dict[str, int] = {}
    clientes_por_nombre: dict[str, set[int]] = {}

    def _proyectar_cliente(fila: dict) -> dict:
        return {campo: fila.get(campo) for campo in CAMPOS_DE_CLIENTE}

    def _insertar_cliente(datos: dict, clave: str) -> int:
        hash_cliente = calcular_hash_fila(
            {campo: datos.get(campo) for campo in ENTIDADES["clientes"].campos_negocio}
        )
        nuevo_id = conexion.execute(
            sa.text(
                "INSERT INTO clientes "
                "(nombre, apellido, correo_electronico, telefono, "
                " numero_pasaporte, clave_natural, hash_fila) "
                "VALUES (:nombre, :apellido, :correo_electronico, :telefono, "
                " :numero_pasaporte, :clave_natural, :hash_fila) "
                "RETURNING id"
            ),
            {
                "nombre": datos.get("nombre"),
                "apellido": datos.get("apellido"),
                "correo_electronico": datos.get("correo_electronico"),
                "telefono": datos.get("telefono"),
                "numero_pasaporte": datos.get("numero_pasaporte"),
                "clave_natural": clave,
                "hash_fila": hash_cliente,
            },
        ).scalar_one()
        clientes_por_clave[clave] = nuevo_id
        clientes_por_nombre.setdefault(
            nombre_canonico(datos.get("nombre"), datos.get("apellido")), set()
        ).add(nuevo_id)
        return nuevo_id

    asignaciones: list[tuple[str, int, int]] = []

    for debiles in (False, True):
        for tabla, filas in filas_por_tabla.items():
            for fila in filas:
                datos_cliente = _proyectar_cliente(fila)
                if clave_es_debil(datos_cliente) is not debiles:
                    continue

                clave = calcular_clave_cliente(datos_cliente)
                cliente_id = clientes_por_clave.get(clave)

                if cliente_id is None and debiles:
                    # No hard identifier: only linked if the name points
                    # to a single already-registered person.
                    candidatos = clientes_por_nombre.get(
                        nombre_canonico(datos_cliente.get("nombre"), datos_cliente.get("apellido")),
                        set(),
                    )
                    if len(candidatos) == 1:
                        cliente_id = next(iter(candidatos))
                        clientes_por_clave[clave] = cliente_id

                if cliente_id is None:
                    cliente_id = _insertar_cliente(datos_cliente, clave)

                asignaciones.append((tabla, int(fila["id"]), cliente_id))

    for tabla, fila_id, cliente_id in asignaciones:
        definicion = ENTIDADES[tabla]
        fila = next(f for f in filas_por_tabla[tabla] if int(f["id"]) == fila_id)
        clave_tramite = calcular_clave_natural(
            tabla, (fila.get(campo) for campo in definicion.campos_clave)
        )
        # The secret field is excluded from the hash: in inherited rows
        # only its ciphertext exists, which isn't comparable across runs
        # because Fernet produces a different ciphertext every time.
        hash_tramite = calcular_hash_fila(
            {
                campo: fila.get(campo)
                for campo in definicion.campos_negocio
                if campo != definicion.campo_secreto
            }
        )
        conexion.execute(
            sa.text(
                f"UPDATE {tabla} SET cliente_id = :cliente_id, "
                "clave_natural = :clave_natural, hash_fila = :hash_fila WHERE id = :id"
            ),
            {
                "cliente_id": cliente_id,
                "clave_natural": clave_tramite,
                "hash_fila": hash_tramite,
                "id": fila_id,
            },
        )

    print(
        f"[migration a1b2c3d4e5f6] {len(clientes_por_clave)} client key(s) "
        f"resolved for {len(asignaciones)} tramite row(s)."
    )

    # -- 4. Archive the duplicates left by the append-only load ------------
    # The previous ETL version inserted blindly, so reprocessing the same
    # Excel file duplicated rows. Now that a natural key exists, those
    # copies are detectable: the oldest one (lowest id, the first one
    # loaded) is kept and the rest are marked deleted. They aren't
    # destroyed: they stay available to audit what was archived and why.
    for tabla in TABLAS_TRAMITE:
        archivados = conexion.execute(
            sa.text(
                f"""
                UPDATE {tabla} SET eliminado_en = CURRENT_TIMESTAMP
                WHERE id NOT IN (
                    SELECT MIN(id) FROM {tabla} GROUP BY clave_natural
                )
                """
            )
        ).rowcount
        if archivados:
            print(
                f"[migration a1b2c3d4e5f6] {tabla}: {archivados} duplicate row(s) "
                "archived for a repeated natural key."
            )

    # -- 5. Tighten constraints once the data has been backfilled ----------
    for tabla in TABLAS_TRAMITE:
        with op.batch_alter_table(tabla) as lote:
            lote.alter_column("cliente_id", existing_type=sa.Integer(), nullable=False)
            lote.alter_column("clave_natural", existing_type=sa.Text(), nullable=False)
            lote.alter_column("hash_fila", existing_type=sa.Text(), nullable=False)
            lote.create_foreign_key(
                f"fk_{tabla}_cliente_id",
                "clientes",
                ["cliente_id"],
                ["id"],
                ondelete="CASCADE",
            )
        op.create_index(f"ix_{tabla}_cliente_id", tabla, ["cliente_id"])
        op.create_index(f"ix_{tabla}_nombre", tabla, ["nombre"])
        op.create_index(f"ix_{tabla}_eliminado_en", tabla, ["eliminado_en"])
        op.create_index(f"ix_{tabla}_cliente_activo", tabla, ["cliente_id", "eliminado_en"])

    op.create_index("ix_pasaportes_fecha_cita", "pasaportes", ["fecha_cita"])

    # -- 6. Partial uniqueness on the natural key ---------------------------
    # Only among active records: that way a current record and its
    # archived versions coexist, and the ETL can point its ON CONFLICT
    # at this index.
    for tabla in ("clientes", *TABLAS_TRAMITE):
        op.create_index(
            f"uq_{tabla}_clave_natural_activa",
            tabla,
            ["clave_natural"],
            unique=True,
            postgresql_where=sa.text("eliminado_en IS NULL"),
            sqlite_where=sa.text("eliminado_en IS NULL"),
        )
        op.create_index(f"ix_{tabla}_clave_natural", tabla, ["clave_natural"])

    # -- 7. Trigram index for search by name --------------------------------
    # Listings filter with ILIKE '%text%', which a B-tree index can't serve
    # because the wildcard is at the start. pg_trgm handles it. Only
    # applies to PostgreSQL; it's skipped on SQLite (used in tests).
    if conexion.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for tabla in ("clientes", *TABLAS_TRAMITE):
            op.execute(
                f"CREATE INDEX ix_{tabla}_nombre_trgm ON {tabla} USING gin (nombre gin_trgm_ops)"
            )


def downgrade() -> None:
    conexion = op.get_bind()

    if conexion.dialect.name == "postgresql":
        for tabla in ("clientes", *TABLAS_TRAMITE):
            op.execute(f"DROP INDEX IF EXISTS ix_{tabla}_nombre_trgm")

    for tabla in ("clientes", *TABLAS_TRAMITE):
        op.drop_index(f"ix_{tabla}_clave_natural", table_name=tabla)
        op.drop_index(f"uq_{tabla}_clave_natural_activa", table_name=tabla)

    op.drop_index("ix_pasaportes_fecha_cita", table_name="pasaportes")

    for tabla in TABLAS_TRAMITE:
        op.drop_index(f"ix_{tabla}_cliente_activo", table_name=tabla)
        op.drop_index(f"ix_{tabla}_eliminado_en", table_name=tabla)
        op.drop_index(f"ix_{tabla}_nombre", table_name=tabla)
        op.drop_index(f"ix_{tabla}_cliente_id", table_name=tabla)
        with op.batch_alter_table(tabla) as lote:
            lote.drop_constraint(f"fk_{tabla}_cliente_id", type_="foreignkey")
        op.drop_column(tabla, "eliminado_en")
        op.drop_column(tabla, "actualizado_en")
        op.drop_column(tabla, "hash_fila")
        op.drop_column(tabla, "clave_natural")
        op.drop_column(tabla, "cliente_id")

    op.drop_index("ix_clientes_eliminado_en", table_name="clientes")
    op.drop_index("ix_clientes_numero_pasaporte", table_name="clientes")
    op.drop_index("ix_clientes_correo_electronico", table_name="clientes")
    op.drop_index("ix_clientes_nombre", table_name="clientes")
    op.drop_table("clientes")
