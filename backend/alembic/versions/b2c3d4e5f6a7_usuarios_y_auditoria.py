"""Anade usuarios con roles y la bitacora de auditoria.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-17 10:20:00.000000

Sustituye la autenticacion basada en dos variables de entorno
(`API_USERNAME` / `API_PASSWORD`) por una tabla de usuarios con hash bcrypt y
roles, y anade `logs_auditoria`.

La bitacora es el motivo de fondo de todo el cambio: el sistema custodia
credenciales de cuentas gubernamentales de clientes reales, y con una sola
cuenta compartida era imposible responder quien consulto que cuenta. Un usuario
por persona hace que la pregunta tenga respuesta.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("admin", "operador")
NIVELES = ("INFO", "ADVERTENCIA", "ALERTA")


def upgrade() -> None:
    # En PostgreSQL, SQLAlchemy emite el CREATE TYPE del ENUM al crear la tabla
    # que lo usa; cada tipo aparece en una sola tabla, asi que no hay conflicto.
    # En SQLite el ENUM degrada a VARCHAR con una restriccion CHECK.
    rol = sa.Enum(*ROLES, name="rol_usuario")
    nivel = sa.Enum(*NIVELES, name="nivel_auditoria")

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("correo_electronico", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        # El nombre de la columna deja explicito en el esquema que aqui nunca
        # hay texto plano.
        sa.Column("contrasena_hash", sa.Text(), nullable=False),
        sa.Column("rol", rol, nullable=False, server_default="operador"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ultimo_acceso_en", sa.DateTime(), nullable=True),
        sa.Column(
            "cargado_en", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("eliminado_en", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correo_electronico", name="uq_usuarios_correo"),
    )
    op.create_index("ix_usuarios_correo_electronico", "usuarios", ["correo_electronico"])
    op.create_index("ix_usuarios_eliminado_en", "usuarios", ["eliminado_en"])

    op.create_table(
        "logs_auditoria",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "ocurrido_en",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        # SET NULL y no CASCADE: dar de baja a alguien no debe borrar el rastro
        # de lo que hizo. Se conserva ademas el correo en texto para que el
        # asiento siga siendo legible sin la fila del usuario.
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_correo", sa.Text(), nullable=True),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("recurso", sa.Text(), nullable=True),
        sa.Column("registro_id", sa.Integer(), nullable=True),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("nivel", nivel, nullable=False, server_default="INFO"),
        sa.Column("direccion_ip", sa.Text(), nullable=True),
        sa.Column("agente_usuario", sa.Text(), nullable=True),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name="fk_logs_auditoria_usuario", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_logs_auditoria_ocurrido_en", "logs_auditoria", ["ocurrido_en"])
    op.create_index("ix_logs_auditoria_accion", "logs_auditoria", ["accion"])
    op.create_index("ix_logs_auditoria_usuario_id", "logs_auditoria", ["usuario_id"])
    op.create_index("ix_logs_auditoria_cliente_id", "logs_auditoria", ["cliente_id"])
    op.create_index("ix_logs_auditoria_recurso", "logs_auditoria", ["recurso", "registro_id"])
    op.create_index(
        "ix_logs_auditoria_usuario_fecha", "logs_auditoria", ["usuario_id", "ocurrido_en"]
    )


def downgrade() -> None:
    conexion = op.get_bind()

    op.drop_index("ix_logs_auditoria_usuario_fecha", table_name="logs_auditoria")
    op.drop_index("ix_logs_auditoria_recurso", table_name="logs_auditoria")
    op.drop_index("ix_logs_auditoria_cliente_id", table_name="logs_auditoria")
    op.drop_index("ix_logs_auditoria_usuario_id", table_name="logs_auditoria")
    op.drop_index("ix_logs_auditoria_accion", table_name="logs_auditoria")
    op.drop_index("ix_logs_auditoria_ocurrido_en", table_name="logs_auditoria")
    op.drop_table("logs_auditoria")

    op.drop_index("ix_usuarios_eliminado_en", table_name="usuarios")
    op.drop_index("ix_usuarios_correo_electronico", table_name="usuarios")
    op.drop_table("usuarios")

    if conexion.dialect.name == "postgresql":
        # Los tipos ENUM de PostgreSQL sobreviven al DROP TABLE, asi que hay que
        # eliminarlos explicitamente. Si no, un `downgrade` seguido de un
        # `upgrade` falla con "type already exists".
        sa.Enum(*NIVELES, name="nivel_auditoria").drop(conexion, checkfirst=True)
        sa.Enum(*ROLES, name="rol_usuario").drop(conexion, checkfirst=True)
