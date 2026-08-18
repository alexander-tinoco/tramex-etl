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

    # TODO(auth): credenciales de un unico administrador tomadas del entorno.
    # Se sustituyen por la tabla `usuarios` con hash bcrypt y roles; se
    # conservan solo para sembrar el primer administrador.
    api_username: str = Field(default="admin", validation_alias="API_USERNAME")
    api_password: str = Field(default="changeme", validation_alias="API_PASSWORD")

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
