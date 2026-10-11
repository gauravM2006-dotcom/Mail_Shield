import base64
import hashlib
import os
import json
from typing import Dict, Any, Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

_hasher = PasswordHasher()

def get_fernet(key: Optional[str] = None) -> Fernet:
    """Return a Fernet cipher instance using key or env."""
    fernet_key = key or os.getenv("FERNET_KEY", "vMy4iU1j_xJqMsmL6U2t1PzQ9Rz-3H6w_t7vU8xY0zA=")
    if isinstance(fernet_key, str):
        fernet_key = fernet_key.encode("utf-8")
    return Fernet(fernet_key)

def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _hasher.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    """Verify a plain password against an Argon2id hash."""
    if not password_hash or not password:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False

def encrypt_data(data: Any, key: Optional[str] = None) -> bytes:
    """Serialize data to JSON and encrypt with Fernet."""
    f = get_fernet(key)
    raw = json.dumps(data).encode("utf-8")
    return f.encrypt(raw)

def decrypt_data(encrypted_bytes: bytes, key: Optional[str] = None) -> Any:
    """Decrypt Fernet-encrypted bytes and parse JSON."""
    if not encrypted_bytes:
        return None
    f = get_fernet(key)
    decrypted = f.decrypt(encrypted_bytes)
    return json.loads(decrypted.decode("utf-8"))

def generate_token(nbytes: int = 32) -> str:
    """Generate a URL-safe random string token."""
    return base64.urlsafe_b64encode(os.urandom(nbytes)).decode("utf-8").rstrip("=")

def hash_token(token: str) -> str:
    """Return SHA-256 hash of a string token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
