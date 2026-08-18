"""
Configuracion de la API, validada al arranque con pydantic-settings.

El arranque es *fail-fast*: si falta una variable obligatoria o una combinacion
es insegura, el proceso no levanta. Es preferible que el despliegue falle de
inmediato y de forma visible a que quede corriendo un servicio que cifra con
una llave de ejemplo o que acepta peticiones autenticadas desde cualquier
origen.
"""

from __future__ import annotations

from typing import Annotated, Literal

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Entorno = Literal["development", "staging", "production"]


class Settings(BaseSettings):
    """Parametros de ejecucion de la API."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../etl/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    version: str = Field(default="2.0.0", description="Version del contrato de la API.")
    entorno: Entorno = Field(default="development", validation_alias="APP_ENV")

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres_password@localhost:5434/tramex"
    )

    #: Llave Fernet con la que se cifran las credenciales de los clientes.
    #: No tiene valor por defecto a proposito: un valor de ejemplo en produccion
    #: significaria que cualquiera con el codigo puede descifrar la base.
    tramex_fernet_key: str = Field(validation_alias="TRAMEX_FERNET_KEY")

    api_secret_key: str = Field(
        default="dev-secret-change-in-production", validation_alias="API_SECRET_KEY"
    )

    #: Origenes autorizados para consumir la API desde un navegador.
    #: En produccion no se admite el comodin: la API responde con credenciales
    #: (cookies y cabecera Authorization) y `*` junto a `allow_credentials`
    #: es una combinacion que los navegadores rechazan y que ademas expondria
    #: la sesion a cualquier sitio.
    #: `NoDecode` desactiva el parseo JSON que pydantic-settings aplica por
    #: defecto a los campos de lista, para poder recibirlos como CSV (que es
    #: como se escriben comodamente en un docker-compose o en un secreto).
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:4200", "http://localhost:8080"],
        validation_alias="ALLOWED_ORIGINS",
    )

    sentry_dsn: str | None = Field(default=None, validation_alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.1, ge=0.0, le=1.0, validation_alias="SENTRY_TRACES_SAMPLE_RATE"
    )

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # -- Sesiones -------------------------------------------------------

    #: Duracion de la sesion. Ocho horas cubre una jornada completa sin obligar
    #: a reautenticar a media tarde, y expira sola al final del dia.
    token_expira_minutos: int = Field(
        default=480, ge=5, le=1440, validation_alias="TOKEN_EXPIRA_MINUTOS"
    )

    #: Coste de bcrypt. 12 rondas es el equilibrio habitual entre resistencia a
    #: fuerza bruta y latencia de login aceptable. Las pruebas lo bajan a 4:
    #: con 12, una suite que inicia sesion decenas de veces tarda medio minuto
    #: solo derivando hashes, y lo que se ejercita ahi es el flujo, no el coste.
    bcrypt_rondas: int = Field(default=12, ge=4, le=16, validation_alias="BCRYPT_RONDAS")

    #: `Secure` exige HTTPS para que el navegador envie la cookie. Se desactiva
    #: solo fuera de produccion, donde se trabaja sobre http://localhost.
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax", validation_alias="COOKIE_SAMESITE"
    )

    # -- Proteccion contra fuerza bruta ----------------------------------

    #: Intentos fallidos consecutivos antes de bloquear temporalmente la cuenta.
    intentos_maximos_login: int = Field(
        default=5, ge=3, le=20, validation_alias="INTENTOS_MAXIMOS_LOGIN"
    )
    #: Ventana en la que se cuentan los intentos y duracion del bloqueo.
    ventana_bloqueo_minutos: int = Field(
        default=15, ge=1, le=120, validation_alias="VENTANA_BLOQUEO_MINUTOS"
    )

    #: Redis respalda el contador de intentos y el limite por IP. Es opcional:
    #: sin el, el contador vive en memoria del proceso, lo que basta para
    #: desarrollo y pruebas pero no coordina varias replicas.
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")

    # -- Retencion de datos personales -----------------------------------

    #: Dias que un registro permanece archivado antes de poder purgarse.
    dias_retencion: int = Field(default=365, ge=30, validation_alias="DIAS_RETENCION")

    # -- Siembra del primer administrador --------------------------------

    #: Correo del primer administrador. El valor por defecto es un dominio
    #: reservado para documentacion: hay que sustituirlo por uno real.
    admin_inicial_correo: str = Field(
        default="admin@example.com", validation_alias="ADMIN_INICIAL_CORREO"
    )
    admin_inicial_contrasena: str | None = Field(
        default=None, validation_alias="ADMIN_INICIAL_CONTRASENA"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _dividir_origenes(cls, valor: object) -> object:
        """Acepta la lista como CSV, que es como se pasa por variable de entorno."""
        if isinstance(valor, str):
            return [origen.strip() for origen in valor.split(",") if origen.strip()]
        return valor

    @field_validator("tramex_fernet_key")
    @classmethod
    def _validar_llave_fernet(cls, valor: str) -> str:
        """Comprueba que la llave sea utilizable antes de que la use el primer request."""
        try:
            Fernet(valor.encode())
        except Exception as exc:
            raise ValueError(
                "TRAMEX_FERNET_KEY no es una llave Fernet valida. "
                "Genera una con `python etl/generate_key.py`."
            ) from exc
        return valor

    @model_validator(mode="after")
    def _validar_coherencia_de_produccion(self) -> Settings:
        """Impide arrancar en produccion con valores pensados para desarrollo."""
        if self.entorno != "production":
            return self

        if self.bcrypt_rondas < 12:
            raise ValueError(
                "BCRYPT_RONDAS no puede bajar de 12 en produccion: el coste de "
                "derivacion es lo que hace inviable un ataque por diccionario."
            )

        problemas: list[str] = []
        if "*" in self.allowed_origins:
            problemas.append(
                "ALLOWED_ORIGINS no puede contener '*' en produccion: la API responde "
                "con credenciales y el comodin las expondria a cualquier origen."
            )
        if self.api_secret_key == "dev-secret-change-in-production":
            problemas.append("API_SECRET_KEY conserva el valor de ejemplo.")
        if self.database_url.startswith("sqlite"):
            problemas.append("DATABASE_URL apunta a SQLite, que no es apto para produccion.")
        if not self.cookie_secure:
            problemas.append(
                "COOKIE_SECURE debe estar activo en produccion: sin el, la cookie de "
                "sesion viajaria por HTTP en claro."
            )
        if self.redis_url is None:
            problemas.append(
                "REDIS_URL es obligatorio en produccion: sin el, el bloqueo por fuerza "
                "bruta vive en memoria de cada replica y se puede eludir rotando de instancia."
            )
        if problemas:
            raise ValueError("Configuracion insegura para produccion: " + " | ".join(problemas))
        return self


try:
    settings = Settings()  # type: ignore[call-arg]
except Exception as exc:
    raise RuntimeError(
        "No se pudo inicializar la configuracion de la API. "
        f"Revisa el archivo .env o las variables de entorno. Detalle: {exc}"
    ) from exc

#: Instancia unica de Fernet. Se crea una sola vez porque derivar la llave en
#: cada peticion seria trabajo redundante.
fernet = Fernet(settings.tramex_fernet_key.encode())
