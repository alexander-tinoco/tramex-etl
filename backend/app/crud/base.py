"""
Capa de repositorio generica.

Toda la logica transversal a las cuatro tablas de tramite vive aqui: identidad
reproducible (`clave_natural` / `hash_fila`), cifrado y descifrado del campo
secreto, borrado logico y busqueda paginada. Los repositorios concretos solo
declaran su modelo y su definicion de entidad; no reimplementan nada de esto.
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

#: Acotado a `RegistroBase` y no a la base declarativa pelada: los metodos de
#: este repositorio leen `id`, `nombre`, `clave_natural` y `eliminado_en`, y
#: solo esa base garantiza que esas columnas existan.
ModelType = TypeVar("ModelType", bound=RegistroBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class ErrorDeDescifrado(Exception):
    """
    El criptograma almacenado no pudo descifrarse con la llave activa.

    Se lanza en vez de devolver `None` porque las dos situaciones son
    radicalmente distintas: "este registro no tiene contrasena" es un dato
    normal, mientras que "hay un criptograma que no abre" significa que la
    llave Fernet fue rotada, que el dato esta corrupto o que se restauro un
    respaldo con otra llave. Silenciarlo haria que el sistema reportara
    "sin contrasena" mientras pierde credenciales de clientes reales.
    """


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Operaciones CRUD comunes sobre un modelo con identidad y borrado logico."""

    def __init__(self, model: type[ModelType], definicion: DefinicionEntidad) -> None:
        self.model = model
        self.definicion = definicion

    # -- Identidad --------------------------------------------------------

    def calcular_identidad(self, datos: dict[str, Any]) -> tuple[str, str]:
        """Devuelve `(clave_natural, hash_fila)` para un diccionario de negocio."""
        clave = calcular_clave_natural(
            self.definicion.tabla,
            (datos.get(campo) for campo in self.definicion.campos_clave),
        )
        contenido = {campo: datos.get(campo) for campo in self.definicion.campos_negocio}
        return clave, calcular_hash_fila(contenido)

    # -- Lectura ----------------------------------------------------------

    def _base_query(self, *, incluir_eliminados: bool = False):
        consulta = select(self.model)
        if not incluir_eliminados:
            consulta = consulta.where(self.model.eliminado_en.is_(None))
        return consulta

    def get(self, db: Session, id: Any, *, incluir_eliminados: bool = False) -> ModelType | None:
        """Obtiene un registro por su clave primaria."""
        consulta = self._base_query(incluir_eliminados=incluir_eliminados)
        return db.scalar(consulta.where(self.model.id == id))

    def get_por_clave_natural(
        self, db: Session, clave_natural: str, *, incluir_eliminados: bool = True
    ) -> ModelType | None:
        """
        Obtiene un registro por su huella de identidad.

        La unicidad de `clave_natural` es parcial (solo entre registros
        activos), asi que una misma identidad puede tener un registro vigente y
        varias versiones archivadas. Se devuelve el vigente si existe y, en su
        defecto, el archivado mas reciente: si el ETL reprocesa una fila que una
        operadora habia dado de baja, corresponde reactivar la existente en vez
        de acumular otra copia.
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
        Lista paginada mas el total de coincidencias.

        `orden="reciente"` devuelve primero lo ultimo tocado. Lo usa el tablero
        de movimientos de la pantalla inicial, cuya pregunta es "que ha pasado
        hoy" y no "cual fue el primer registro que se cargo".
        """
        consulta = self._base_query(incluir_eliminados=incluir_eliminados)
        if buscar:
            consulta = consulta.where(self.model.nombre.ilike(f"%{buscar}%"))
        if cliente_id is not None and hasattr(self.model, "cliente_id"):
            # `cliente_id` existe en las cuatro tablas de tramite pero no en
            # `clientes`, que es la raiz; de ahi la comprobacion previa y este
            # silenciador acotado a esa linea.
            consulta = consulta.where(self.model.cliente_id == cliente_id)  # type: ignore[attr-defined]

        total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0

        criterio: tuple[Any, ...]
        if orden == "reciente":
            # El id se mantiene como desempate para que el orden sea total y la
            # paginacion no repita ni se salte filas cuando varias comparten
            # marca de tiempo, que es lo normal tras una carga del ETL.
            criterio = (self.model.actualizado_en.desc(), self.model.id.desc())
        else:
            criterio = (self.model.id,)

        registros: Sequence[ModelType] = db.scalars(
            consulta.order_by(*criterio).offset(skip).limit(limit)
        ).all()
        return list(registros), total

    # -- Escritura --------------------------------------------------------

    def _preparar(self, datos: dict[str, Any]) -> dict[str, Any]:
        """
        Traduce un diccionario de negocio a columnas persistibles.

        Cifra el campo secreto y calcula las huellas de identidad. El hash se
        calcula *antes* del cifrado: Fernet usa un IV aleatorio, asi que el
        criptograma cambia en cada llamada y compararlo siempre indicaria
        "modificado".
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
        """Crea un registro nuevo con identidad y cifrado ya resueltos."""
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
        Actualiza parcialmente un registro (semantica PATCH).

        `exclude_unset=True` distingue "campo ausente en la peticion" (se deja
        como esta) de "campo enviado explicitamente como null" (se borra), que
        son intenciones distintas y no deben confundirse.
        """
        if isinstance(obj_in, dict):
            cambios = dict(obj_in)
        else:
            cambios = obj_in.model_dump(exclude_unset=True)

        # Se parte del estado actual para que las huellas reflejen la fila
        # completa resultante y no solo el subconjunto enviado.
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
        Reconstruye el diccionario de negocio de un registro persistido.

        El campo secreto se recupera descifrado para que un PATCH que no lo
        incluya no invalide el hash de la fila.
        """
        datos: dict[str, Any] = {}
        for campo in self.definicion.campos_negocio:
            if campo == self.definicion.campo_secreto:
                datos[campo] = self.descifrar_secreto(db_obj, estricto=False)
            else:
                datos[campo] = getattr(db_obj, campo, None)
        return datos

    # -- Borrado logico ---------------------------------------------------

    def remove(self, db: Session, *, id: int) -> ModelType | None:
        """
        Marca el registro como eliminado sin destruirlo.

        Se conserva para trazabilidad: en un sistema con datos personales, un
        borrado accidental debe poder revertirse y una baja debe poder
        auditarse. La destruccion fisica ocurre en `purgar`.
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
        """Revierte un borrado logico."""
        registro = self.get(db, id, incluir_eliminados=True)
        if registro is None or registro.eliminado_en is None:
            return None
        registro.eliminado_en = None
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro

    def purgar(self, db: Session, *, id: int) -> ModelType | None:
        """Destruye fisicamente un registro ya marcado como eliminado."""
        registro = self.get(db, id, incluir_eliminados=True)
        if registro is None or registro.eliminado_en is None:
            return None
        db.delete(registro)
        db.commit()
        return registro

    def purgar_vencidos(self, db: Session, *, antes_de: datetime) -> int:
        """
        Purga los registros borrados logicamente antes de una fecha de corte.

        Es el mecanismo con el que se aplica la politica de retencion.
        Devuelve cuantas filas se destruyeron.
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

    # -- Secreto ----------------------------------------------------------

    def descifrar_secreto(self, db_obj: ModelType, *, estricto: bool = True) -> str | None:
        """
        Descifra la credencial almacenada.

        Devuelve `None` unicamente cuando el registro no tiene criptograma. Si
        hay criptograma pero no abre con la llave activa, lanza
        `ErrorDeDescifrado` en modo estricto: es un fallo de infraestructura
        (llave rotada, dato corrupto, respaldo ajeno) y debe escalar, no
        confundirse con la ausencia de contrasena.
        """
        if self.definicion.campo_secreto is None:
            return None
        criptograma = getattr(db_obj, "contrasena_cifrada", None)
        if not criptograma:
            return None
        try:
            return fernet.decrypt(criptograma.encode()).decode()
        except Exception as exc:  # InvalidToken y errores de codificacion
            if estricto:
                raise ErrorDeDescifrado(
                    f"El criptograma de {self.definicion.tabla}#{db_obj.id} no pudo "
                    "descifrarse con la llave activa (TRAMEX_FERNET_KEY)."
                ) from exc
            return None
