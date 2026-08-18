"""
Repositorio de clientes y resolucion de identidad.

Aqui vive la respuesta a la pregunta que el Excel original no podia contestar:
"estas cuatro filas, en cuatro pestanas distintas, son la misma persona?".
Tanto el ETL como la API pasan por `resolver_o_crear`, de modo que ambos
convergen sobre el mismo cliente en lugar de crear uno por cada punto de
entrada.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models import Cliente
from app.schemas import ClienteCreate, ClienteUpdate
from tramex_shared import (
    CLIENTES,
    calcular_clave_cliente,
    calcular_hash_fila,
    clave_es_debil,
    nombre_canonico,
)


class CRUDCliente(CRUDBase[Cliente, ClienteCreate, ClienteUpdate]):
    """Repositorio de la entidad raiz del modelo."""

    def calcular_identidad(self, datos: dict[str, Any]) -> tuple[str, str]:
        """
        La identidad de una persona no se deriva de sus campos en crudo.

        Se usa el nombre canonico (nombre y apellido unidos y normalizados, para
        que "José Ramírez" y "Ana"/"Lopez" sean comparables entre hojas) mas el
        identificador duro disponible. Por eso este metodo sustituye al generico
        de `CRUDBase`.
        """
        contenido = {campo: datos.get(campo) for campo in CLIENTES.campos_negocio}
        return calcular_clave_cliente(datos), calcular_hash_fila(contenido)

    def buscar_por_nombre_canonico(self, db: Session, datos: dict[str, Any]) -> list[Cliente]:
        """
        Candidatos activos cuyo nombre canonico coincide exactamente.

        Se usa solo para resolver registros sin identificador duro. La
        comparacion se hace en Python, no en SQL, porque la normalizacion
        (acentos, espacios) debe ser identica a la del resto del pipeline y
        reimplementarla en SQL abriria una segunda fuente de verdad.
        """
        objetivo = nombre_canonico(datos.get("nombre"), datos.get("apellido"))
        if not objetivo:
            return []
        activos = db.scalars(select(Cliente).where(Cliente.eliminado_en.is_(None))).all()
        return [
            cliente
            for cliente in activos
            if nombre_canonico(cliente.nombre, cliente.apellido) == objetivo
        ]

    def resolver_o_crear(self, db: Session, datos: dict[str, Any]) -> Cliente:
        """
        Devuelve el cliente al que pertenece un registro de tramite.

        Estrategia en dos pasadas:

        1. Coincidencia exacta por clave natural. Resuelve el caso normal, en el
           que el registro trae pasaporte o correo.
        2. Solo si el registro no trae ningun identificador duro, se busca por
           nombre canonico entre los clientes activos. Si hay **exactamente un**
           candidato, se enlaza a el: es el caso de la hoja de Pasaportes, que
           no captura pasaporte y quedaria desconectada del resto.
           Si hay varios candidatos la situacion es ambigua (homonimos), y se
           prefiere crear una persona nueva antes que fusionar por error los
           expedientes de dos clientes distintos. Corregirlo despues es trivial;
           deshacer una fusion equivocada no lo es.

        Un cliente encontrado pero dado de baja se reactiva: que se archive un
        tramite no significa que la persona deje de existir.
        """
        proyeccion = {campo: datos.get(campo) for campo in CLIENTES.campos_negocio}
        clave_natural, _ = self.calcular_identidad(proyeccion)

        existente = self.get_por_clave_natural(db, clave_natural)

        if existente is None and clave_es_debil(proyeccion):
            candidatos = self.buscar_por_nombre_canonico(db, proyeccion)
            if len(candidatos) == 1:
                return candidatos[0]

        if existente is not None:
            if existente.eliminado_en is not None:
                existente.eliminado_en = None
                db.add(existente)
                db.commit()
                db.refresh(existente)
            return existente

        return self.create(db, obj_in=proyeccion)


crud_cliente = CRUDCliente(Cliente, CLIENTES)
