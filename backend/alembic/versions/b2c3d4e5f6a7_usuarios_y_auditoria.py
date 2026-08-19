"""Adds users with roles and the audit log.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-17 10:20:00.000000

Replaces authentication based on two environment variables
(`API_USERNAME` / `API_PASSWORD`) with a users table with bcrypt hashing
and roles, and adds `logs_auditoria`.

The audit log is the underlying reason for the whole change: the system
holds credentials for real clients' government accounts, and with a single
shared account it was impossible to answer who looked up which account.
One user per person means the question has an answer.
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
    # On PostgreSQL, SQLAlchemy emits the ENUM's CREATE TYPE when creating
    # the table that uses it; each type appears in only one table, so
    # there's no conflict. On SQLite the ENUM degrades to VARCHAR with a
    # CHECK constraint.
    rol = sa.Enum(*ROLES, name="rol_usuario")
    nivel = sa.Enum(*NIVELES, name="nivel_auditoria")

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("correo_electronico", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        # The column name makes it explicit in the schema that this never
        # holds plaintext.
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
    # No separate index is created on the email: the UNIQUE constraint
    # already carries its own, and duplicating it only adds writes on
    # every insert.
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
        # SET NULL, not CASCADE: deactivating someone must not erase the
        # trace of what they did. The email is also kept as plain text so
        # the entry stays legible without the user's row.
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
    op.drop_table("usuarios")

    if conexion.dialect.name == "postgresql":
        # PostgreSQL's ENUM types survive DROP TABLE, so they must be
        # dropped explicitly. Otherwise a `downgrade` followed by an
        # `upgrade` fails with "type already exists".
        sa.Enum(*NIVELES, name="nivel_auditoria").drop(conexion, checkfirst=True)
        sa.Enum(*ROLES, name="rol_usuario").drop(conexion, checkfirst=True)
