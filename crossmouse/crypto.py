from __future__ import annotations

import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT_SIZE = 16
NONCE_SIZE = 12
PBKDF2_ROUNDS = 210_000
HANDSHAKE_AAD = b"crossmouse-handshake-v1"
MESSAGE_AAD = b"crossmouse-message-v1"


def derive_key(secret: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"), salt, PBKDF2_ROUNDS, dklen=32
    )


def new_salt() -> bytes:
    return os.urandom(SALT_SIZE)


def seal(key: bytes, plaintext: bytes, aad: bytes = MESSAGE_AAD) -> bytes:
    nonce = os.urandom(NONCE_SIZE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def open_sealed(key: bytes, blob: bytes, aad: bytes = MESSAGE_AAD) -> bytes:
    if len(blob) < NONCE_SIZE:
        raise ValueError("sealed blob too short")
    return AESGCM(key).decrypt(blob[:NONCE_SIZE], blob[NONCE_SIZE:], aad)


def make_probe(key: bytes) -> bytes:
    return seal(key, b"crossmouse-probe", HANDSHAKE_AAD)


def verify_probe(key: bytes, blob: bytes) -> bool:
    try:
        return open_sealed(key, blob, HANDSHAKE_AAD) == b"crossmouse-probe"
    except Exception:
        return False
