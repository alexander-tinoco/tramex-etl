"""
Client repository and identity resolution.

This is where the question the original Excel couldn't answer gets solved:
"are these four rows, in four different sheets, the same person?". Both the
ETL and the API go through `resolver_o_crear`, so they converge on the same
client instead of creating one per entry point.
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
    """Repository for the model's root entity."""

    def calcular_identidad(self, datos: dict[str, Any]) -> tuple[str, str]:
        """
        A person's identity is not derived from their raw fields.

        Uses the canonical name (first and last name joined and normalized,
        so "José Ramírez" and "Ana"/"Lopez" are comparable across sheets)
        plus whatever hard identifier is available. That's why this method
        overrides `CRUDBase`'s generic one.
        """
        contenido = {campo: datos.get(campo) for campo in CLIENTES.campos_negocio}
        return calcular_clave_cliente(datos), calcular_hash_fila(contenido)

    def buscar_por_nombre_canonico(self, db: Session, datos: dict[str, Any]) -> list[Cliente]:
        """
        Active candidates whose canonical name matches exactly.

        Used only to resolve records with no hard identifier. The comparison
        is done in Python, not SQL, because the normalization (accents,
        spaces) must be identical to the rest of the pipeline, and
        reimplementing it in SQL would open a second source of truth.
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
        Returns the client a tramite record belongs to.

        Two-pass strategy:

        1. Exact match by natural key. Handles the normal case, where the
           record carries a passport or email.
        2. Only if the record carries no hard identifier at all, look up by
           canonical name among active clients. If there is **exactly one**
           candidate, link to it: this is the case of the Passports sheet,
           which doesn't capture a passport number and would otherwise be
           disconnected from the rest.
           If there are several candidates the situation is ambiguous
           (namesakes), and creating a new person is preferred over
           mistakenly merging two different clients' records. Fixing that
           later is trivial; undoing a wrong merge is not.

        A client that is found but archived gets reactivated: archiving one
        tramite doesn't mean the person stops existing.
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
