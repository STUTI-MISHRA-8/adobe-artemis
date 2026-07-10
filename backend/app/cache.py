import hashlib


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
