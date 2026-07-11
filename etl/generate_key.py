"""
Genera una llave de cifrado para el campo de contraseñas.

Uso:
    python generate_key.py

Guarda el resultado como variable de entorno TRAMEX_FERNET_KEY
(en tu gestor de secretos, NUNCA en el código ni en el repositorio).
Si pierdes esta llave, las contraseñas cifradas ya guardadas no se
podrán volver a leer, así que respáldala en un lugar seguro
(ej. Vaultwarden, un vault de la empresa) y no solo en el .env local.
"""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key().decode()
    print("Nueva llave generada. Guárdala como TRAMEX_FERNET_KEY:\n")
    print(key)
