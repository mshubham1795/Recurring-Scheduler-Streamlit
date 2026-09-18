"""
Credential encryption using Fernet symmetric encryption.
Key is loaded from environment variable SCHEDULER_ENCRYPTION_KEY.
For local development, auto-generates and persists a key file.
"""
import os
import logging
from pathlib import Path

from cryptography.fernet import Fernet

from config.constants import ENCRYPTION_KEY_ENV, DB_DIR

log = logging.getLogger("SASBackend")

_cached_key = None


def _get_key() -> bytes:
    """Load encryption key from environment or local key file."""
    global _cached_key
    if _cached_key:
        return _cached_key

    # Try environment variable first (production / Posit Connect)
    key = os.environ.get(ENCRYPTION_KEY_ENV)
    if key:
        _cached_key = key.encode() if isinstance(key, str) else key
        return _cached_key

    # Fallback: local key file for development
    key_file = DB_DIR / ".encryption_key"
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
    else:
        key = Fernet.generate_key().decode()
        DB_DIR.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key, encoding="utf-8")
        log.warning(
            "[CRYPTO] Generated new encryption key at %s. "
            "For production, set %s environment variable.",
            key_file, ENCRYPTION_KEY_ENV
        )

    _cached_key = key.encode() if isinstance(key, str) else key
    return _cached_key


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential string. Returns base64-encoded ciphertext."""
    f = Fernet(_get_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a credential string. Returns plaintext."""
    f = Fernet(_get_key())
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
