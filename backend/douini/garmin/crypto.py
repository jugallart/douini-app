from __future__ import annotations

import logging

from cryptography.fernet import Fernet

from douini.settings import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key = settings.DOUINI_ENCRYPTION_KEY
    if not key:
        if settings.is_prod:
            raise RuntimeError("DOUINI_ENCRYPTION_KEY required in prod")
        key = Fernet.generate_key().decode()
        logger.warning("DEV MODE — generated ephemeral encryption key")

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_token(raw: str) -> str:
    return get_fernet().encrypt(raw.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()
