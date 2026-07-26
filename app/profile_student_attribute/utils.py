import base64
import binascii
import logging

from app.core.utils.encrypt import Enciphering, is_sensitive_key

logger = logging.getLogger(__name__)

_cipher = Enciphering()


def is_already_encrypted(value: str | None) -> bool:
    if not value:
        return False

    try:
        decrypted = _cipher._decrypt(value)
        if decrypted != value:
            return True
    except Exception:
        pass

    try:
        decoded = base64.b64decode(value)

        if len(decoded) >= 32:
            try:
                text = decoded.decode('utf-8')
                if any(c in text for c in [' ', ',', '.', 'á', 'é', 'í', 'ó', 'ú']):
                    return False
            except UnicodeDecodeError:
                return True
    except (binascii.Error, Exception):
        return False

    return False


def encrypt_if_sensitive(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if is_sensitive_key(key):
        return _cipher._encrypt(value)
    return value


def decrypt_if_sensitive(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not is_sensitive_key(key):
        return value
    try:
        return _cipher._decrypt(value)
    except Exception as exc:
        logger.warning(
            "Decryption failed for key '%s': %s. Returning raw value.",
            key, exc,
        )
        return value
