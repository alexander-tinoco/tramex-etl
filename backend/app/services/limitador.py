"""
Limitacion de intentos: fuerza bruta y saturacion del endpoint de login.

El login era el punto mas expuesto de la API: publico, sin limite de intentos y
sin bloqueo. Cualquiera podia probar contrasenas indefinidamente.

Se implementan dos controles complementarios:

* **Bloqueo por cuenta.** Tras N fallos consecutivos en una ventana, esa cuenta
  queda bloqueada aunque el atacante rote de IP.
* **Limite por IP.** Acota el ritmo de peticiones desde un mismo origen, lo que
  frena el barrido de muchas cuentas distintas.

El contador vive en Redis cuando esta configurado, para que varias replicas
compartan el estado. Sin Redis se usa un respaldo en memoria del proceso: sirve
en desarrollo y pruebas, pero no coordina replicas, y por eso la configuracion
exige Redis en produccion.
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
    """Resultado de consultar el limitador."""

    permitido: bool
    intentos: int = 0
    segundos_restantes: int = 0


class AlmacenDeContadores(Protocol):
    """Contrato minimo que necesita el limitador de su almacen."""

    def incrementar(self, clave: str, ttl_segundos: int) -> int: ...

    def leer(self, clave: str) -> int: ...

    def ttl(self, clave: str) -> int: ...

    def borrar(self, clave: str) -> None: ...


@dataclass
class AlmacenEnMemoria:
    """
    Respaldo en memoria del proceso.

    Deliberadamente simple: no hay hilo de limpieza, las entradas caducadas se
    descartan al leerlas. Para el volumen de un endpoint de login es suficiente
    y evita una dependencia mas en desarrollo.
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
            # La ventana arranca con el primer fallo y no se renueva con los
            # siguientes: de lo contrario un atacante constante la extenderia
            # para siempre y la cuenta nunca se desbloquearia.
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
    """Contadores compartidos entre replicas."""

    def __init__(self, url: str) -> None:
        import redis

        self._cliente = redis.Redis.from_url(url, decode_responses=True)

    def incrementar(self, clave: str, ttl_segundos: int) -> int:
        tuberia = self._cliente.pipeline()
        tuberia.incr(clave)
        # `nx` deja intacto el vencimiento si la ventana ya estaba abierta.
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
            logger.info("Limitador respaldado por Redis")
            return almacen
        except Exception as exc:
            # Que Redis no responda no debe tumbar la API, pero si debe verse:
            # el sistema queda operando con un control degradado.
            logger.error("No se pudo conectar a Redis; se usara memoria local", exc_info=exc)
    logger.warning("Limitador en memoria: no coordina varias replicas")
    return AlmacenEnMemoria()


_almacen: AlmacenDeContadores | None = None


def obtener_almacen() -> AlmacenDeContadores:
    """Devuelve el almacen activo, creandolo la primera vez."""
    global _almacen
    if _almacen is None:
        _almacen = _construir_almacen()
    return _almacen


def reiniciar_almacen(almacen: AlmacenDeContadores | None = None) -> None:
    """Sustituye el almacen. Pensado para aislar las pruebas entre si."""
    global _almacen
    _almacen = almacen


def _clave_cuenta(correo: str) -> str:
    return f"tramex:login:cuenta:{correo.strip().lower()}"


def _clave_ip(ip: str) -> str:
    return f"tramex:login:ip:{ip}"


def estado_de_cuenta(correo: str) -> Veredicto:
    """Consulta si una cuenta esta bloqueada, sin contar un intento nuevo."""
    almacen = obtener_almacen()
    clave = _clave_cuenta(correo)
    intentos = almacen.leer(clave)
    if intentos >= settings.intentos_maximos_login:
        return Veredicto(False, intentos, almacen.ttl(clave))
    return Veredicto(True, intentos, 0)


def registrar_fallo(correo: str, ip: str) -> Veredicto:
    """Cuenta un intento fallido y devuelve el estado resultante de la cuenta."""
    almacen = obtener_almacen()
    ttl = settings.ventana_bloqueo_minutos * 60
    intentos = almacen.incrementar(_clave_cuenta(correo), ttl)
    almacen.incrementar(_clave_ip(ip), ttl)

    if intentos >= settings.intentos_maximos_login:
        logger.warning(
            "Cuenta bloqueada por intentos fallidos",
            extra={"intentos": intentos, "ventana_minutos": settings.ventana_bloqueo_minutos},
        )
        return Veredicto(False, intentos, almacen.ttl(_clave_cuenta(correo)))
    return Veredicto(True, intentos, 0)


def registrar_exito(correo: str) -> None:
    """Un login correcto limpia el contador de la cuenta."""
    obtener_almacen().borrar(_clave_cuenta(correo))


def estado_de_ip(ip: str) -> Veredicto:
    """
    Limite por origen.

    El umbral es mas alto que el de cuenta porque una oficina entera puede
    compartir IP publica y un dia de trabajo normal acumula varios logins.
    """
    almacen = obtener_almacen()
    clave = _clave_ip(ip)
    intentos = almacen.leer(clave)
    limite = settings.intentos_maximos_login * 4
    if intentos >= limite:
        return Veredicto(False, intentos, almacen.ttl(clave))
    return Veredicto(True, intentos, 0)
