"""
Metricas en formato Prometheus.

El proyecto ya emitia logs estructurados y reportaba excepciones a Sentry, pero
no exponia nada agregable: no habia forma de responder "cuantas peticiones por
segundo aguanta", "que percentil de latencia tiene el listado" ni, sobre todo,
"cuantas credenciales de clientes se consultaron esta semana".

Esa ultima es la razon de que este modulo exista: la bitacora de auditoria
guarda el detalle por asiento, pero una serie temporal permite ver la tendencia
y alertar si el volumen se dispara.
"""

from __future__ import annotations

from collections.abc import Mapping

from prometheus_client import CollectorRegistry, Counter, Histogram, multiprocess
from prometheus_client.core import REGISTRY

#: Cubetas ajustadas a un CRUD sobre PostgreSQL: la mayoria de las peticiones
#: cae por debajo de 100 ms, asi que el detalle util esta en ese rango. Las
#: cubetas por defecto de la libreria se concentran en segundos y dejarian casi
#: todo el trafico en el primer intervalo.
CUBETAS_LATENCIA = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

#: `prometheus_client` anade el sufijo `_total` a los contadores al exponerlos,
#: asi que el nombre en Python no debe llevarlo ya: se expone como
#: `tramex_peticiones_total`.
peticiones_totales = Counter(
    "tramex_peticiones",
    "Peticiones HTTP atendidas.",
    ["metodo", "ruta", "codigo"],
)

duracion_peticiones = Histogram(
    "tramex_duracion_peticiones_segundos",
    "Latencia de las peticiones HTTP.",
    ["metodo", "ruta"],
    buckets=CUBETAS_LATENCIA,
)

credenciales_consultadas = Counter(
    "tramex_credenciales_consultadas",
    "Descifrados de credenciales de clientes, por recurso y resultado.",
    ["recurso", "resultado"],
)

intentos_de_login = Counter(
    "tramex_intentos_login",
    "Intentos de inicio de sesion, por resultado.",
    ["resultado"],
)


def normalizar_ruta(ruta: str, parametros: Mapping[str, object]) -> str:
    """
    Devuelve la plantilla de la ruta en lugar de la URL concreta.

    Sin esto, `/api/v1/canada/1` y `/api/v1/canada/2` serian series distintas y
    la cardinalidad de la metrica creceria con cada registro de la base, que es
    la forma habitual de tumbar un Prometheus.

    Se reconstruye sustituyendo los segmentos que coinciden con un parametro de
    ruta, en lugar de leer `scope["route"].path`: cuando los routers se incluyen
    con prefijo, ese atributo devuelve la ruta local (`/{registro_id}`) y los
    cuatro recursos colisionarian en la misma serie.

    >>> normalizar_ruta("/api/v1/canada/7", {"registro_id": 7})
    '/api/v1/canada/{registro_id}'
    >>> normalizar_ruta("/health", {})
    '/health'
    """
    if not parametros:
        return ruta

    por_valor = {str(valor): nombre for nombre, valor in parametros.items()}
    segmentos = [por_valor.get(segmento, segmento) for segmento in ruta.split("/")]
    return "/".join(
        f"{{{segmento}}}" if segmento in parametros else segmento for segmento in segmentos
    )


def registro() -> CollectorRegistry:
    """Registro de metricas activo."""
    if multiprocess is None:  # pragma: no cover - depende del despliegue
        return REGISTRY
    return REGISTRY
