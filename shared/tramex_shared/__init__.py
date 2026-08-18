"""Codigo compartido entre el pipeline ETL y la API de Tramex."""

from tramex_shared.esquema import (
    CANADA,
    CLIENTES,
    ENTIDADES,
    GLOBAL_ENTRY,
    MASTER_TRAMEX,
    PASAPORTES,
    DefinicionEntidad,
)
from tramex_shared.identidad import (
    calcular_clave_cliente,
    calcular_clave_natural,
    calcular_hash_fila,
    clave_es_debil,
    identificador_fuerte,
    nombre_canonico,
    normalizar_identificador,
)

__all__ = [
    "CANADA",
    "CLIENTES",
    "ENTIDADES",
    "GLOBAL_ENTRY",
    "MASTER_TRAMEX",
    "PASAPORTES",
    "DefinicionEntidad",
    "calcular_clave_cliente",
    "calcular_clave_natural",
    "calcular_hash_fila",
    "clave_es_debil",
    "identificador_fuerte",
    "nombre_canonico",
    "normalizar_identificador",
]
