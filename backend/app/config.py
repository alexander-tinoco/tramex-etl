"""
API configuration, validated at startup with pydantic-settings.

Startup is *fail-fast*: if a required variable is missing or a combination is
unsafe, the process refuses to come up. It's better for the deployment to fail
immediately and visibly than to end up running a service that encrypts with an
example key or accepts authenticated requests from any origin.
"""

from __future__ import annotations

from typing import Annotated, Literal

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Entorno = Literal["development", "staging", "production"]


class Settings(BaseSettings):
    """API runtime parameters."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../etl/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    version: str = Field(default="2.0.0", description="API contract version.")
    entorno: Entorno = Field(default="development", validation_alias="APP_ENV")

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres_password@localhost:5434/tramex"
    )

    #: Fernet key used to encrypt clients' credentials.
    #: Deliberately has no default: an example value in production would mean
    #: anyone with the code could decrypt the database.
    tramex_fernet_key: str = Field(validation_alias="TRAMEX_FERNET_KEY")

    api_secret_key: str = Field(
        default="dev-secret-change-in-production", validation_alias="API_SECRET_KEY"
    )

    #: Origins authorized to consume the API from a browser.
    #: In production the wildcard is not allowed: the API responds with
    #: credentials (cookies and an Authorization header), and `*` alongside
    #: `allow_credentials` is a combination browsers reject and that would
    #: also expose the session to any site.
    #: `NoDecode` turns off the JSON parsing pydantic-settings applies by
    #: default to list fields, so they can be received as CSV (which is how
    #: they're comfortably written in a docker-compose file or a secret).
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:4200", "http://localhost:8080"],
        validation_alias="ALLOWED_ORIGINS",
    )

    sentry_dsn: str | None = Field(default=None, validation_alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.1, ge=0.0, le=1.0, validation_alias="SENTRY_TRACES_SAMPLE_RATE"
    )

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # -- Sessions ---------------------------------------------------------

    #: Session duration. Eight hours covers a full workday without forcing a
    #: mid-afternoon reauthentication, and expires on its own by day's end.
    token_expira_minutos: int = Field(
        default=480, ge=5, le=1440, validation_alias="TOKEN_EXPIRA_MINUTOS"
    )

    #: bcrypt cost. 12 rounds is the usual balance between brute-force
    #: resistance and acceptable login latency. Tests lower it to 4: at 12, a
    #: suite that signs in dozens of times takes half a minute just deriving
    #: hashes, and what's being exercised there is the flow, not the cost.
    bcrypt_rondas: int = Field(default=12, ge=4, le=16, validation_alias="BCRYPT_RONDAS")

    #: `Secure` requires HTTPS for the browser to send the cookie. It's only
    #: disabled outside production, where work happens over http://localhost.
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax", validation_alias="COOKIE_SAMESITE"
    )

    # -- Brute-force protection -------------------------------------------

    #: Consecutive failed attempts before temporarily locking the account.
    intentos_maximos_login: int = Field(
        default=5, ge=3, le=20, validation_alias="INTENTOS_MAXIMOS_LOGIN"
    )
    #: Window over which attempts are counted, and lockout duration.
    ventana_bloqueo_minutos: int = Field(
        default=15, ge=1, le=120, validation_alias="VENTANA_BLOQUEO_MINUTOS"
    )

    #: Redis backs the attempt counter and the per-IP rate limit. It's
    #: optional: without it, the counter lives in process memory, which is
    #: enough for development and tests but doesn't coordinate across replicas.
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")

    # -- Personal data retention -------------------------------------------

    #: Days a record stays archived before it can be purged.
    dias_retencion: int = Field(default=365, ge=30, validation_alias="DIAS_RETENCION")

    # -- First administrator seed -------------------------------------------

    #: First administrator's email. The default value is a domain reserved
    #: for documentation: it must be replaced with a real one.
    admin_inicial_correo: str = Field(
        default="admin@example.com", validation_alias="ADMIN_INICIAL_CORREO"
    )
    admin_inicial_contrasena: str | None = Field(
        default=None, validation_alias="ADMIN_INICIAL_CONTRASENA"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _dividir_origenes(cls, valor: object) -> object:
        """Accepts the list as CSV, which is how it's passed via environment variable."""
        if isinstance(valor, str):
            return [origen.strip() for origen in valor.split(",") if origen.strip()]
        return valor

    @field_validator("tramex_fernet_key")
    @classmethod
    def _validar_llave_fernet(cls, valor: str) -> str:
        """Checks that the key is usable before the first request touches it."""
        try:
            Fernet(valor.encode())
        except Exception as exc:
            raise ValueError(
                "TRAMEX_FERNET_KEY is not a valid Fernet key. "
                "Generate one with `python etl/generate_key.py`."
            ) from exc
        return valor

    @model_validator(mode="after")
    def _validar_coherencia_de_produccion(self) -> Settings:
        """Prevents starting up in production with values meant for development."""
        if self.entorno != "production":
            return self

        if self.bcrypt_rondas < 12:
            raise ValueError(
                "BCRYPT_RONDAS cannot go below 12 in production: the derivation "
                "cost is what makes a dictionary attack infeasible."
            )

        problemas: list[str] = []
        if "*" in self.allowed_origins:
            problemas.append(
                "ALLOWED_ORIGINS cannot contain '*' in production: the API "
                "responds with credentials and the wildcard would expose them "
                "to any origin."
            )
        if self.api_secret_key == "dev-secret-change-in-production":
            problemas.append("API_SECRET_KEY still holds the example value.")
        if self.database_url.startswith("sqlite"):
            problemas.append("DATABASE_URL points to SQLite, which is not fit for production.")
        if not self.cookie_secure:
            problemas.append(
                "COOKIE_SECURE must be on in production: without it, the "
                "session cookie would travel over plain HTTP."
            )
        if self.redis_url is None:
            problemas.append(
                "REDIS_URL is required in production: without it, the "
                "brute-force lockout lives in each replica's memory and can be "
                "sidestepped by rotating instances."
            )
        if problemas:
            raise ValueError("Unsafe configuration for production: " + " | ".join(problemas))
        return self


try:
    settings = Settings()  # type: ignore[call-arg]
except Exception as exc:
    raise RuntimeError(
        "Could not initialize the API configuration. "
        f"Check the .env file or the environment variables. Detail: {exc}"
    ) from exc

#: Single Fernet instance. Created once, since deriving the key on every
#: request would be redundant work.
fernet = Fernet(settings.tramex_fernet_key.encode())
