"""
Metrics in Prometheus format.

The project already emitted structured logs and reported exceptions to
Sentry, but exposed nothing aggregable: there was no way to answer "how
many requests per second can this handle", "what latency percentile does
the listing have", or, above all, "how many client credentials were looked
up this week".

That last one is the reason this module exists: the audit log keeps the
per-entry detail, but a time series lets you see the trend and alert if
the volume spikes.
"""

from __future__ import annotations

from collections.abc import Mapping

from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.core import REGISTRY

#: Buckets tuned for a CRUD app on PostgreSQL: most requests fall under
#: 100 ms, so that's where the useful detail is. The library's default
#: buckets are concentrated in seconds and would dump nearly all traffic
#: into the first interval.
CUBETAS_LATENCIA = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

#: `prometheus_client` appends the `_total` suffix to counters when exposing
#: them, so the Python name shouldn't already carry it: it's exposed as
#: `tramex_peticiones_total`.
peticiones_totales = Counter(
    "tramex_peticiones",
    "HTTP requests served.",
    ["metodo", "ruta", "codigo"],
)

duracion_peticiones = Histogram(
    "tramex_duracion_peticiones_segundos",
    "Latency of HTTP requests.",
    ["metodo", "ruta"],
    buckets=CUBETAS_LATENCIA,
)

credenciales_consultadas = Counter(
    "tramex_credenciales_consultadas",
    "Client credential decryptions, by resource and outcome.",
    ["recurso", "resultado"],
)

intentos_de_login = Counter(
    "tramex_intentos_login",
    "Sign-in attempts, by outcome.",
    ["resultado"],
)


def normalizar_ruta(ruta: str, parametros: Mapping[str, object]) -> str:
    """
    Returns the route template instead of the concrete URL.

    Without this, `/api/v1/canada/1` and `/api/v1/canada/2` would be
    different series and the metric's cardinality would grow with every
    row in the database, which is the usual way to take down a Prometheus.

    It's rebuilt by substituting the segments that match a route parameter,
    instead of reading `scope["route"].path`: when routers are included
    with a prefix, that attribute returns the local route (`/{registro_id}`)
    and the four resources would collide into the same series.

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
    """
    The active metrics registry.

    It's the library's global registry. With several uvicorn workers, each
    process exposes its own counters, so Prometheus will see one series per
    replica; consolidating them would require enabling prometheus_client's
    multiprocess mode, which needs a shared directory and buys nothing while
    the deployment scales by containers rather than by processes.
    """
    return REGISTRY
