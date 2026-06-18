import os
from cryptography.fernet import Fernet

def _get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY not found in environment. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())

def encrypt_value(plain_text: str) -> str:
    """Encrypt a string and return the token as a UTF-8 string."""
    return _get_fernet().encrypt(plain_text.encode()).decode()

def decrypt_value(encrypted_text: str) -> str:
    """Decrypt a Fernet token back to the original string."""
    return _get_fernet().decrypt(encrypted_text.encode()).decode()