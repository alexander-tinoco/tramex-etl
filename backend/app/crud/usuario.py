"""
Repositorio de usuarios.

No hereda de `CRUDBase` porque los usuarios no participan del pipeline de
ingesta: no tienen clave natural ni hash de fila, y su alta nunca viene del
Excel. Forzar la herencia solo para reutilizar dos metodos habria arrastrado
columnas que no significan nada en esta tabla.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Rol, Usuario
from app.schemas import UsuarioCreate, UsuarioUpdate
from app.security import hashear_contrasena


class CRUDUsuario:
    """Acceso a la tabla de usuarios."""

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
        """Da de alta un usuario. La contrasena se hashea antes de tocar la sesion."""
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
        Baja logica del usuario.

        No se elimina la fila: la bitacora de auditoria referencia al autor de
        cada evento, y destruirlo dejaria asientos historicos sin responsable.
        """
        usuario.activo = False
        usuario.eliminado_en = datetime.now(UTC)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    def contar_admins_activos(self, db: Session) -> int:
        """Cuenta administradores vigentes, para no dejar el sistema sin ninguno."""
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
