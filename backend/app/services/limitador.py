"""
Attempt limiting: brute force and saturation of the login endpoint.

Login was the API's most exposed point: public, with no attempt limit and
no lockout. Anyone could try passwords indefinitely.

Two complementary controls are implemented:

* **Account lockout.** After N consecutive failures in a window, that
  account gets locked even if the attacker rotates IPs.
* **Per-IP limit.** Caps the request rate from a single origin, which
  slows down sweeping many different accounts.

The counter lives in Redis when configured, so several replicas share the
state. Without Redis, an in-process memory fallback is used: it works for
development and tests, but doesn't coordinate replicas, which is why the
configuration requires Redis in production.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Protocol

from app.config import settings

logger = logging.getLogger("tramex_api.limitador")


@dataclass
class Veredicto:
    """Result of querying the limiter."""

    permitido: bool
    intentos: int = 0
    segundos_restantes: int = 0


class AlmacenDeContadores(Protocol):
    """Minimal contract the limiter needs from its store."""

    def incrementar(self, clave: str, ttl_segundos: int) -> int: ...

    def leer(self, clave: str) -> int: ...

    def ttl(self, clave: str) -> int: ...

    def borrar(self, clave: str) -> None: ...


@dataclass
class AlmacenEnMemoria:
    """
    In-process memory fallback.

    Deliberately simple: there's no cleanup thread, expired entries are
    dropped when read. For the volume of a login endpoint that's enough,
    and it avoids one more dependency in development.
    """

    _datos: dict[str, tuple[int, float]] = field(default_factory=dict)

    def _vigente(self, clave: str) -> tuple[int, float] | None:
        entrada = self._datos.get(clave)
        if entrada is None:
            return None
        if entrada[1] <= time.monotonic():
            self._datos.pop(clave, None)
            return None
        return entrada

    def incrementar(self, clave: str, ttl_segundos: int) -> int:
        entrada = self._vigente(clave)
        if entrada is None:
            # The window starts on the first failure and isn't renewed by
            # later ones: otherwise a persistent attacker would extend it
            # forever and the account would never unlock.
            self._datos[clave] = (1, time.monotonic() + ttl_segundos)
            return 1
        conteo, expira = entrada
        self._datos[clave] = (conteo + 1, expira)
        return conteo + 1

    def leer(self, clave: str) -> int:
        entrada = self._vigente(clave)
        return entrada[0] if entrada else 0

    def ttl(self, clave: str) -> int:
        entrada = self._vigente(clave)
        return max(0, int(entrada[1] - time.monotonic())) if entrada else 0

    def borrar(self, clave: str) -> None:
        self._datos.pop(clave, None)


class AlmacenRedis:
    """Counters shared across replicas."""

    def __init__(self, url: str) -> None:
        import redis

        self._cliente = redis.Redis.from_url(url, decode_responses=True)

    def incrementar(self, clave: str, ttl_segundos: int) -> int:
        tuberia = self._cliente.pipeline()
        tuberia.incr(clave)
        # `nx` leaves the expiration untouched if the window was already open.
        tuberia.expire(clave, ttl_segundos, nx=True)
        conteo, _ = tuberia.execute()
        return int(conteo)

    def leer(self, clave: str) -> int:
        valor = self._cliente.get(clave)
        return int(valor) if valor else 0

    def ttl(self, clave: str) -> int:
        return max(0, int(self._cliente.ttl(clave) or 0))

    def borrar(self, clave: str) -> None:
        self._cliente.delete(clave)


def _construir_almacen() -> AlmacenDeContadores:
    if settings.redis_url:
        try:
            almacen = AlmacenRedis(settings.redis_url)
            logger.info("Limiter backed by Redis")
            return almacen
        except Exception as exc:
            # Redis being unreachable shouldn't take the API down, but it
            # must be visible: the system keeps running with a degraded
            # control.
            logger.error("Could not connect to Redis; falling back to local memory", exc_info=exc)
    logger.warning("Limiter running in memory: does not coordinate multiple replicas")
    return AlmacenEnMemoria()


_almacen: AlmacenDeContadores | None = None


def obtener_almacen() -> AlmacenDeContadores:
    """Returns the active store, creating it the first time."""
    global _almacen
    if _almacen is None:
        _almacen = _construir_almacen()
    return _almacen


def reiniciar_almacen(almacen: AlmacenDeContadores | None = None) -> None:
    """Replaces the store. Meant to isolate tests from each other."""
    global _almacen
    _almacen = almacen


def _clave_cuenta(correo: str) -> str:
    return f"tramex:login:cuenta:{correo.strip().lower()}"


def _clave_ip(ip: str) -> str:
    return f"tramex:login:ip:{ip}"


def estado_de_cuenta(correo: str) -> Veredicto:
    """Checks whether an account is locked, without counting a new attempt."""
    almacen = obtener_almacen()
    clave = _clave_cuenta(correo)
    intentos = almacen.leer(clave)
    if intentos >= settings.intentos_maximos_login:
        return Veredicto(False, intentos, almacen.ttl(clave))
    return Veredicto(True, intentos, 0)


def registrar_fallo(correo: str, ip: str) -> Veredicto:
    """Counts a failed attempt and returns the account's resulting state."""
    almacen = obtener_almacen()
    ttl = settings.ventana_bloqueo_minutos * 60
    intentos = almacen.incrementar(_clave_cuenta(correo), ttl)
    almacen.incrementar(_clave_ip(ip), ttl)

    if intentos >= settings.intentos_maximos_login:
        logger.warning(
            "Account locked due to failed attempts",
            extra={"intentos": intentos, "ventana_minutos": settings.ventana_bloqueo_minutos},
        )
        return Veredicto(False, intentos, almacen.ttl(_clave_cuenta(correo)))
    return Veredicto(True, intentos, 0)


def registrar_exito(correo: str) -> None:
    """A successful login clears the account's counter."""
    obtener_almacen().borrar(_clave_cuenta(correo))


def estado_de_ip(ip: str) -> Veredicto:
    """
    Per-origin limit.

    The threshold is higher than the per-account one because a whole office
    can share a public IP, and a normal workday racks up several logins.
    """
    almacen = obtener_almacen()
    clave = _clave_ip(ip)
    intentos = almacen.leer(clave)
    limite = settings.intentos_maximos_login * 4
    if intentos >= limite:
        return Veredicto(False, intentos, almacen.ttl(clave))
    return Veredicto(True, intentos, 0)
