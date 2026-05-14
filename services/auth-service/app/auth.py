from datetime import datetime, timedelta, timezone
from typing import Optional

import redis as redis_lib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_security = HTTPBearer()

# ── 비밀번호 ──────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────

def _make_token(user_id: str, token_type: str, expire: timedelta) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    return _make_token(user_id, "access", timedelta(minutes=settings.JWT_EXPIRE))


def create_refresh_token(user_id: str) -> str:
    settings = get_settings()
    return _make_token(user_id, "refresh", timedelta(days=settings.REFRESH_EXPIRE))


def decode_token(token: str, expected_type: str) -> dict:
    """
    토큰 검증.
    - 만료: 401 "Token expired"
    - 타입 불일치: 401 "Invalid token type"
    - 그 외 유효하지 않음: 401 "Invalid token"
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    return payload


# ── Redis (Refresh Token 저장소) ─────────────

def _get_redis() -> redis_lib.Redis:
    settings = get_settings()
    # Redis DB 0번 사용 (URL에 /0 포함)
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _refresh_key(user_id: str) -> str:
    return f"refresh:{user_id}"


def store_refresh_token(user_id: str, token: str) -> None:
    settings = get_settings()
    r = _get_redis()
    expire_seconds = settings.REFRESH_EXPIRE * 24 * 60 * 60
    r.setex(_refresh_key(user_id), expire_seconds, token)


def get_stored_refresh_token(user_id: str) -> Optional[str]:
    return _get_redis().get(_refresh_key(user_id))


def delete_refresh_token(user_id: str) -> None:
    _get_redis().delete(_refresh_key(user_id))


# ── FastAPI Dependency ────────────────────────

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    payload = decode_token(credentials.credentials, "access")
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user_id
