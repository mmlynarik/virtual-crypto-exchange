import hashlib
import hmac
import logging
import secrets
import unicodedata

# Same scrypt parameters as the web app's hasher (web/src/lib/auth/passwordHasher.ts)
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 64


def get_logger(name: str, level: int | None = None):
    logger = logging.getLogger(name)

    if level is None:
        level = 20

    logger.setLevel(level)

    return logger


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.scrypt(
        unicodedata.normalize("NFC", password).encode(),
        salt=salt.encode(),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_KEY_LENGTH,
    ).hex()


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), hashed_password)
