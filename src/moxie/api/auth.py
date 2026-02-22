from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from moxie.api.settings import get_settings

password_hasher = PasswordHash.recommended()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8  # One login per work shift (user decision)


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2."""
    return password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its Argon2 hash."""
    return password_hasher.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    """Create a signed JWT for the given user_id with 8-hour expiry."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """Decode a JWT and return the user_id (int).

    Raises jwt.exceptions.InvalidTokenError if the token is invalid or expired.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    sub = payload.get("sub")
    if sub is None:
        raise jwt.exceptions.InvalidTokenError("No sub claim in token")
    return int(sub)
