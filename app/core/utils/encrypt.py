import base64

from Crypto.Cipher import AES

from app.core.config import get_settings

settings = get_settings()


SENSITIVE_KEY_SET = frozenset({
    "full_name",
    "email",
    "phone",
    "location",
})


def is_sensitive_key(key: str) -> bool:
    if key in SENSITIVE_KEY_SET:
        return True
    segments = key.split(".")
    for i in range(len(segments), 0, -1):
        prefix = ".".join(segments[:i])
        if prefix in SENSITIVE_KEY_SET:
            return True
    return False


class Enciphering:
    def __init__(self):
        self._encryption_key: bytes | None = None

    def _get_cypher_key(self) -> bytes | None:
        if self._encryption_key is not None:
            return self._encryption_key

        raw = settings.ENCRYPTION_KEY
        if not raw:
            self._encryption_key = None
            return None

        self._encryption_key = base64.b64decode(raw)
        if len(self._encryption_key) != 32:
            raise ValueError("The encryption key must be 32 bytes long after base64 decoding.")
        return self._encryption_key

    def _encrypt(self, plaintext: str) -> str:
        key = self._get_cypher_key()
        if key is None:
            return plaintext

        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
        payload = cipher.nonce + tag + ciphertext
        return base64.b64encode(payload).decode("ascii")

    def _decrypt(self, encrypted_b64: str) -> str:
        key = self._get_cypher_key()
        if key is None:
            return encrypted_b64

        data = base64.b64decode(encrypted_b64)
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
