import uuid
from datetime import UTC, datetime

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import settings
from core.core.permissions import Permission, get_permissions_for_role
from core.core.security import decode_access_token, verify_token
from core.models.auth_models import APIKey, User
from core.repositories.auth import AuthRepository
from core.storage.postgres import get_db

oauth2_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_auth_repo(db: AsyncSession = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)


async def get_current_identity(
    request: Request,
    token: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    api_key_str: str | None = Depends(api_key_header),
    repo: AuthRepository = Depends(get_auth_repo),
) -> User | APIKey:
    """
    Hardened Identity Resolver.
    Supports asymmetric JWTs and high-entropy API keys.
    """
    # 1. Try JWT Auth (Human Session)
    if token:
        try:
            payload = decode_access_token(token.credentials)
            user_id = payload.get("sub")
            token_v = payload.get("v")
            
            if not user_id or token_v is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")
                
            user = await repo.get_user_by_id(uuid.UUID(user_id))
            
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
            
            # GLOBAL REVOCATION CHECK (Token Versioning)
            if user.token_version != token_v:
                await repo.log_audit_event(
                    "STALE_TOKEN_USED", "WARNING", user.id, severity="MEDIUM",
                    details={"token_v": token_v, "user_v": user.token_version}
                )
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
            
            return user
            
        except jwt.PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail=f"Invalid credentials: {str(e)}"
            ) from e

    # 2. Try API Key Auth (Machine/System)
    elif api_key_str:
        if len(api_key_str) < 20:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key format")
            
        prefix = api_key_str[:10]
        api_key_obj = await repo.get_api_key_by_prefix(prefix)
        
        if not api_key_obj or not api_key_obj.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API Key")
            
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key expired")
            
        # Verify HMAC-SHA256 Hash
        if not verify_token(api_key_str, api_key_obj.key_hash, settings.API_KEY_PEPPER):
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
            
        # Update usage telemetry (non-blocking in high volume ideally, but here sync-ish)
        api_key_obj.last_used_at = datetime.now(UTC)
        await repo.update_api_key(api_key_obj)
        
        return api_key_obj
        
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def get_current_user(
    identity: User | APIKey = Depends(get_current_identity)
) -> User:
    """Strictly requires a human user session."""
    if isinstance(identity, APIKey):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API Keys not allowed for this operation")
    return identity


def require_permissions(required: list[Permission]):
    """
    Hardened Permission Guard.
    Works for both human Users (via Role) and API Keys (via Scopes).
    """
    async def permission_checker(identity: User | APIKey = Depends(get_current_identity)):
        if isinstance(identity, User):
            user_perms = get_permissions_for_role(identity.role.value)
            missing = [p for p in required if p not in user_perms]
        else:
            # API Key scopes are string-based. Map them to Permission enum.
            key_scopes = set(identity.scopes)
            missing = [p for p in required if p.value not in key_scopes]
            
        if missing:
            logger.warning("SECURITY | Permission denied", extra={"identity_id": str(identity.id), "missing": [p.value for p in missing]})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Insufficient privileges"
            )
        return identity
        
    return permission_checker
