"""
Generic repository layer.

All the logic shared by the four tramite tables lives here: reproducible
identity (`clave_natural` / `hash_fila`), encrypting and decrypting the secret
field, soft delete and paginated search. The concrete repositories only
declare their model and their entity definition; none of this gets
reimplemented.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import fernet
from app.models import RegistroBase
from tramex_shared import DefinicionEntidad, calcular_clave_natural, calcular_hash_fila

#: Bound to `RegistroBase` rather than the bare declarative base: this
#: repository's methods read `id`, `nombre`, `clave_natural` and
#: `eliminado_en`, and only that base guarantees those columns exist.
ModelType = TypeVar("ModelType", bound=RegistroBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class ErrorDeDescifrado(Exception):
    """
    The stored ciphertext could not be decrypted with the active key.

    Raised instead of returning `None` because the two situations are
    radically different: "this record has no password" is a normal state,
    while "there's a ciphertext that won't open" means the Fernet key was
    rotated, the data is corrupted, or a backup encrypted with a different
    key was restored. Silencing it would make the system report "no
    password" while actually losing real clients' credentials.
    """


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Common CRUD operations on a model with identity and soft delete."""

    def __init__(self, model: type[ModelType], definicion: DefinicionEntidad) -> None:
        self.model = model
        self.definicion = definicion

    # -- Identity -----------------------------------------------------------

    def calcular_identidad(self, datos: dict[str, Any]) -> tuple[str, str]:
        """Returns `(clave_natural, hash_fila)` for a business dict."""
        clave = calcular_clave_natural(
            self.definicion.tabla,
            (datos.get(campo) for campo in self.definicion.campos_clave),
        )
        contenido = {campo: datos.get(campo) for campo in self.definicion.campos_negocio}
        return clave, calcular_hash_fila(contenido)

    # -- Reads ----------------------------------------------------------

    def _base_query(self, *, incluir_eliminados: bool = False):
        consulta = select(self.model)
        if not incluir_eliminados:
            consulta = consulta.where(self.model.eliminado_en.is_(None))
        return consulta

    def get(self, db: Session, id: Any, *, incluir_eliminados: bool = False) -> ModelType | None:
        """Fetches a record by its primary key."""
        consulta = self._base_query(incluir_eliminados=incluir_eliminados)
        return db.scalar(consulta.where(self.model.id == id))

    def get_por_clave_natural(
        self, db: Session, clave_natural: str, *, incluir_eliminados: bool = True
    ) -> ModelType | None:
        """
        Fetches a record by its identity fingerprint.

        Uniqueness of `clave_natural` is partial (only among active records),
        so the same identity can have one current record and several
        archived versions. The current one is returned if it exists;
        otherwise, the most recently archived one: if the ETL reprocesses a
        row that an operator had archived, the right move is to reactivate
        the existing record rather than pile up another copy.
        """
        consulta = self._base_query(incluir_eliminados=incluir_eliminados).where(
            self.model.clave_natural == clave_natural
        )
        consulta = consulta.order_by(self.model.eliminado_en.is_(None).desc(), self.model.id.desc())
        return db.scalars(consulta.limit(1)).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        buscar: str | None = None,
        cliente_id: int | None = None,
        incluir_eliminados: bool = False,
        orden: str = "id",
    ) -> tuple[list[ModelType], int]:
        """
        Paginated list plus the total match count.

        `orden="reciente"` returns whatever was touched last, first. It's
        used by the recent-activity board on the landing screen, whose
        question is "what happened today", not "what was the first record
        ever loaded".
        """
        consulta = self._base_query(incluir_eliminados=incluir_eliminados)
        if buscar:
            consulta = consulta.where(self.model.nombre.ilike(f"%{buscar}%"))
        if cliente_id is not None and hasattr(self.model, "cliente_id"):
            # `cliente_id` exists on the four tramite tables but not on
            # `clientes`, which is the root; hence the guard above and this
            # `type: ignore` scoped to just this line.
            consulta = consulta.where(self.model.cliente_id == cliente_id)  # type: ignore[attr-defined]

        total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0

        criterio: tuple[Any, ...]
        if orden == "reciente":
            # `id` stays as the tiebreaker so the order is total and
            # pagination doesn't repeat or skip rows when several share a
            # timestamp, which is normal after an ETL load.
            criterio = (self.model.actualizado_en.desc(), self.model.id.desc())
        else:
            criterio = (self.model.id,)

        registros: Sequence[ModelType] = db.scalars(
            consulta.order_by(*criterio).offset(skip).limit(limit)
        ).all()
        return list(registros), total

    # -- Writes --------------------------------------------------------

    def _preparar(self, datos: dict[str, Any]) -> dict[str, Any]:
        """
        Translates a business dict into persistable columns.

        Encrypts the secret field and computes the identity fingerprints.
        The hash is computed *before* encryption: Fernet uses a random IV, so
        the ciphertext changes on every call, and comparing it would always
        say "modified".
        """
        preparado = dict(datos)
        clave_natural, hash_fila = self.calcular_identidad(preparado)

        secreto = self.definicion.campo_secreto
        if secreto is not None:
            valor = preparado.pop(secreto, None)
            if valor:
                preparado["contrasena_cifrada"] = fernet.encrypt(str(valor).encode()).decode()

        preparado["clave_natural"] = clave_natural
        preparado["hash_fila"] = hash_fila
        return preparado

    def create(self, db: Session, *, obj_in: CreateSchemaType | dict[str, Any]) -> ModelType:
        """Creates a new record with identity and encryption already resolved."""
        datos = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()
        registro = self.model(**self._preparar(datos))
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        """
        Partially updates a record (PATCH semantics).

        `exclude_unset=True` distinguishes "field absent from the request"
        (left as-is) from "field explicitly sent as null" (erased), which
        are different intentions and must not be conflated.
        """
        if isinstance(obj_in, dict):
            cambios = dict(obj_in)
        else:
            cambios = obj_in.model_dump(exclude_unset=True)

        # Starts from the current state so the fingerprints reflect the
        # resulting full row, not just the submitted subset.
        estado = self.exportar_negocio(db_obj)
        estado.update(cambios)

        for columna, valor in self._preparar(estado).items():
            if hasattr(db_obj, columna):
                setattr(db_obj, columna, valor)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def exportar_negocio(self, db_obj: ModelType) -> dict[str, Any]:
        """
        Rebuilds the business dict of a persisted record.

        The secret field is recovered decrypted so a PATCH that doesn't
        include it doesn't invalidate the row hash.
        """
        datos: dict[str, Any] = {}
        for campo in self.definicion.campos_negocio:
            if campo == self.definicion.campo_secreto:
                datos[campo] = self.descifrar_secreto(db_obj, estricto=False)
            else:
                datos[campo] = getattr(db_obj, campo, None)
        return datos

    # -- Soft delete ---------------------------------------------------

    def remove(self, db: Session, *, id: int) -> ModelType | None:
        """
        Marks the record as deleted without destroying it.

        Kept for traceability: in a system with personal data, an accidental
        deletion must be reversible and an archival must be auditable.
        Physical destruction happens in `purgar`.
        """
        registro = self.get(db, id)
        if registro is None:
            return None
        registro.eliminado_en = datetime.now(UTC)
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro

    def restore(self, db: Session, *, id: int) -> ModelType | None:
        """Reverts a soft delete."""
        registro = self.get(db, id, incluir_eliminados=True)
        if registro is None or registro.eliminado_en is None:
            return None
        registro.eliminado_en = None
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro

    def purgar(self, db: Session, *, id: int) -> ModelType | None:
        """Physically destroys a record already marked as deleted."""
        registro = self.get(db, id, incluir_eliminados=True)
        if registro is None or registro.eliminado_en is None:
            return None
        db.delete(registro)
        db.commit()
        return registro

    def purgar_vencidos(self, db: Session, *, antes_de: datetime) -> int:
        """
        Purges records soft-deleted before a cutoff date.

        This is the mechanism that enforces the retention policy. Returns how
        many rows were destroyed.
        """
        vencidos = db.scalars(
            select(self.model).where(
                self.model.eliminado_en.is_not(None),
                self.model.eliminado_en < antes_de,
            )
        ).all()
        for registro in vencidos:
            db.delete(registro)
        db.commit()
        return len(vencidos)

    # -- Secret ----------------------------------------------------------

    def descifrar_secreto(self, db_obj: ModelType, *, estricto: bool = True) -> str | None:
        """
        Decrypts the stored credential.

        Returns `None` only when the record has no ciphertext. If there's a
        ciphertext but it won't open with the active key, raises
        `ErrorDeDescifrado` in strict mode: that's an infrastructure failure
        (rotated key, corrupted data, someone else's backup) and must
        surface, not be mistaken for the absence of a password.
        """
        if self.definicion.campo_secreto is None:
            return None
        criptograma = getattr(db_obj, "contrasena_cifrada", None)
        if not criptograma:
            return None
        try:
            return fernet.decrypt(criptograma.encode()).decode()
        except Exception as exc:  # InvalidToken and encoding errors
            if estricto:
                raise ErrorDeDescifrado(
                    f"The ciphertext for {self.definicion.tabla}#{db_obj.id} could not "
                    "be decrypted with the active key (TRAMEX_FERNET_KEY)."
                ) from exc
            return None
