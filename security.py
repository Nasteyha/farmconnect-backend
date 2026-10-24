import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()

ALGORITHM = "HS256"
TOKEN_LIFETIME_MINUTES = 60


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # stored value isn't a valid bcrypt hash
        return False


def _secret_key() -> str:
    # Read when a token is made or checked (not when the file is imported),
    # so scripts that only hash passwords don't need SECRET_KEY.
    key = os.getenv("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY is not set. Add it to the .env file.")
    return key


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),  # "subject": who this token belongs to
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_LIFETIME_MINUTES),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str):
    """Return the token's contents, or None if it is fake, altered or expired."""
    try:
        return jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None