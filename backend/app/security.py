"""
Utilidades de seguridad: JWT + validación de credenciales.

Las credenciales de acceso a la API se toman de variables de entorno:
  API_USERNAME  (default: admin)
  API_PASSWORD  (default: changeme)
  API_SECRET_KEY  (default: dev-secret — cambiar en producción)

No se usa una tabla de usuarios para mantener la simplicidad.
"""

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

SECRET_KEY: str = settings.api_secret_key
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS: int = 24

API_USERNAME: str = settings.api_username
API_PASSWORD: str = settings.api_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ---------------------------------------------------------------------------
# Funciones de token
# ---------------------------------------------------------------------------


def create_access_token(data: dict) -> str:
    """Crea un JWT firmado con expiración de ACCESS_TOKEN_EXPIRE_HOURS horas."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Dependencia de FastAPI: valida el JWT y retorna el username del payload.

    Lanza HTTP 401 si el token es inválido, expirado o malformado.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError as exc:
        raise credentials_exception from exc
