"""
Configuración de la aplicación Tramex API utilizando Pydantic Settings.
Garantiza tipos correctos, validaciones y valores predeterminados.
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    # Carga de variables desde archivos .env en orden de prioridad
    model_config = SettingsConfigDict(
        env_file=(".env", "../etl/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres_password@localhost:5434/tramex"
    )
    
    tramex_fernet_key: str = Field(validation_alias="TRAMEX_FERNET_KEY")
    
    api_secret_key: str = Field(
        default="dev-secret-change-in-production",
        validation_alias="API_SECRET_KEY"
    )
    
    api_username: str = Field(
        default="admin",
        validation_alias="API_USERNAME"
    )
    
    api_password: str = Field(
        default="changeme",
        validation_alias="API_PASSWORD"
    )

    # Configuración de CORS permitidos para entornos de producción
    allowed_origins: List[str] = Field(
        default=["*"],
        validation_alias="ALLOWED_ORIGINS"
    )


# Instanciar configuraciones validadas
try:
    settings = Settings()
    # Instancia global de Fernet para cifrar / descifrar contraseñas
    fernet = Fernet(settings.tramex_fernet_key.encode())
except Exception as e:
    raise RuntimeError(
        f"Falta inicializar variables obligatorias en el entorno o en el archivo .env. "
        f"Detalle del error de configuración: {e}"
    )
