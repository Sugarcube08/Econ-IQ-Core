import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from loguru import logger

from core.config.settings import settings

# --- OTP HARDENING: HMAC-SHA256 (Fast & Efficient) ---

def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return f"{secrets.randbelow(1000000):06d}"


def hash_otp(otp: str) -> str:
    """
    Fast HMAC-SHA256 hashing for short-lived OTPs.
    Uses a pepper from settings to protect against DB leaks.
    """
    return hmac.new(
        settings.OTP_PEPPER.encode(),
        otp.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    """Constant-time verification of OTP."""
    return secrets.compare_digest(hash_otp(plain_otp), hashed_otp)


# --- JWT HARDENING: EdDSA (Asymmetric) ---

def _get_key_hash(key: str | None) -> str:
    """Helper to get a safe diagnostic hash of a key."""
    if not key:
        return "MISSING"
    clean_key = key.replace("\\n", "\n").strip()
    return hashlib.sha256(clean_key.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Creates a hardened EdDSA JWT.
    Injects standard security claims: sub, iat, exp, iss, aud, jti.
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": secrets.token_urlsafe(16)
    })
    
    # DIAGNOSTIC LOGGING
    logger.debug(
        "SECURITY | JWT sign details",
        extra={
            "alg": settings.JWT_ALGORITHM,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "priv_hash": _get_key_hash(settings.JWT_PRIVATE_KEY)
        }
    )

    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_PRIVATE_KEY.replace("\\n", "\n").strip(), 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT using the public EdDSA key.
    Enforces strict audience and issuer validation.
    """
    # DIAGNOSTIC LOGGING
    logger.debug(
        "SECURITY | JWT verify details",
        extra={
            "alg": settings.JWT_ALGORITHM,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "pub_hash": _get_key_hash(settings.JWT_PUBLIC_KEY)
        }
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY.replace("\\n", "\n").strip(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            leeway=10,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
                "verify_nbf": True,
            }
        )
        return payload
    except jwt.PyJWTError as e:
        logger.warning("SECURITY | JWT validation failed", extra={"error": str(e)})
        raise


# --- REFRESH & API KEY HARDENING: HMAC-SHA256 ---

def generate_refresh_token() -> str:
    """Generate a high-entropy cryptographically secure refresh token."""
    return secrets.token_urlsafe(64)


def hash_token(token: str, pepper: str) -> str:
    """
    Securely hash a token (refresh or API key) using HMAC-SHA256 + Pepper.
    Deterministic for fast DB lookup.
    """
    return hmac.new(
        pepper.encode(),
        token.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_token(plain_token: str, hashed_token: str, pepper: str) -> bool:
    """Verify a plain token against its HMAC-SHA256 hash."""
    return secrets.compare_digest(hash_token(plain_token, pepper), hashed_token)


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a production-grade API key.
    Returns: (prefix, raw_key, hashed_key)
    """
    raw_key = f"gr_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:10]  # gr_ + 7 chars
    hashed_key = hash_token(raw_key, settings.API_KEY_PEPPER)
    return prefix, raw_key, hashed_key
