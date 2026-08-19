"""
User repository.

Doesn't inherit from `CRUDBase` because users don't take part in the ingest
pipeline: they have no natural key or row hash, and they're never created
from the Excel. Forcing the inheritance just to reuse two methods would have
dragged in columns that mean nothing on this table.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Rol, Usuario
from app.schemas import UsuarioCreate, UsuarioUpdate
from app.security import hashear_contrasena


class CRUDUsuario:
    """Access to the users table."""

    def get(self, db: Session, usuario_id: int) -> Usuario | None:
        return db.scalar(
            select(Usuario).where(Usuario.id == usuario_id, Usuario.eliminado_en.is_(None))
        )

    def get_por_correo(self, db: Session, correo: str) -> Usuario | None:
        return db.scalar(
            select(Usuario).where(
                Usuario.correo_electronico == correo.strip().lower(),
                Usuario.eliminado_en.is_(None),
            )
        )

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> tuple[list[Usuario], int]:
        consulta = select(Usuario).where(Usuario.eliminado_en.is_(None))
        total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        usuarios = db.scalars(consulta.order_by(Usuario.id).offset(skip).limit(limit)).all()
        return list(usuarios), total

    def create(self, db: Session, *, datos: UsuarioCreate) -> Usuario:
        """Creates a user. The password is hashed before touching the session."""
        usuario = Usuario(
            correo_electronico=datos.correo_electronico.strip().lower(),
            nombre=datos.nombre,
            contrasena_hash=hashear_contrasena(datos.contrasena),
            rol=Rol(datos.rol),
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    def update(self, db: Session, *, usuario: Usuario, datos: UsuarioUpdate) -> Usuario:
        cambios = datos.model_dump(exclude_unset=True)
        if "rol" in cambios and cambios["rol"] is not None:
            cambios["rol"] = Rol(cambios["rol"])
        for campo, valor in cambios.items():
            setattr(usuario, campo, valor)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    def cambiar_contrasena(self, db: Session, *, usuario: Usuario, nueva: str) -> Usuario:
        usuario.contrasena_hash = hashear_contrasena(nueva)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    def registrar_acceso(self, db: Session, *, usuario: Usuario) -> None:
        usuario.ultimo_acceso_en = datetime.now(UTC)
        db.add(usuario)
        db.commit()

    def desactivar(self, db: Session, *, usuario: Usuario) -> Usuario:
        """
        Soft-deactivates the user.

        The row is not removed: the audit log references the author of each
        event, and destroying it would leave historical entries without an
        owner.
        """
        usuario.activo = False
        usuario.eliminado_en = datetime.now(UTC)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    def contar_admins_activos(self, db: Session) -> int:
        """Counts active administrators, so the system is never left without one."""
        return (
            db.scalar(
                select(func.count())
                .select_from(Usuario)
                .where(
                    Usuario.rol == Rol.ADMIN,
                    Usuario.activo.is_(True),
                    Usuario.eliminado_en.is_(None),
                )
            )
            or 0
        )


crud_usuario = CRUDUsuario()
