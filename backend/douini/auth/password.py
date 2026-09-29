from __future__ import annotations

import bcrypt

_COMMON = frozenset(
    {
        "password", "123456", "12345678", "qwerty", "abc123",
        "password1", "111111", "123456789", "1234567", "admin",
        "letmein", "welcome", "monkey", "dragon", "master",
    }
)


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(raw.encode()[:72], hashed.encode())


def is_common_password(raw: str) -> bool:
    return raw.lower().strip() in _COMMON
