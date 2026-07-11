"""
Router de autenticación.

POST /api/auth/token  →  Retorna un JWT Bearer si las credenciales son correctas.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.security import API_PASSWORD, API_USERNAME, create_access_token

router = APIRouter(tags=["Auth"])


@router.post("/token", summary="Obtener token de acceso")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Autenticarse con usuario y contraseña para recibir un JWT.

    Las credenciales se configuran mediante las variables de entorno
    `API_USERNAME` y `API_PASSWORD`.
    """
    if form_data.username != API_USERNAME or form_data.password != API_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}
