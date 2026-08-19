"""
Generates an encryption key for the password field.

Usage:
    python generate_key.py

Save the result as the TRAMEX_FERNET_KEY environment variable
(in your secrets manager, NEVER in the code or the repository).
If you lose this key, credentials already encrypted with it can never
be read again, so back it up somewhere safe (e.g. Vaultwarden, a
company vault) and not only in the local .env file.
"""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key().decode()
    print("New key generated. Save it as TRAMEX_FERNET_KEY:\n")
    print(key)
