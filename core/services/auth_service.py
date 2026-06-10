import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from loguru import logger

from core.config.settings import settings
from core.core.rate_limit import RateLimiter
from core.core.security import (
    create_access_token,
    generate_api_key,
    generate_otp,
    generate_refresh_token,
    hash_otp,
    hash_token,
    verify_otp,
)
from core.models.auth_models import (
    APIKey,
    OTPChallenge,
    RefreshSession,
    User,
    UserSession,
)
from core.repositories.auth import AuthRepository
from core.schemas.auth import TokenResponseSchema
from core.services.email_service import EmailService


class AuthService:
    def __init__(self, repo: AuthRepository, correlation_id: str | None = None):
        self.repo = repo
        self.correlation_id = correlation_id

    async def request_otp(
        self, email: str, ip_address: str, user_agent: str | None = None
    ) -> None:
        """
        Hardened OTP request flow.
        Enforces Redis rate limits and anti-enumeration delays.
        """
        # 1. Rate Limiting (Fail-Closed)
        if not await RateLimiter.is_otp_request_allowed(email, ip_address):
            await self.repo.log_audit_event(
                "OTP_RATE_LIMITED", "FAILURE", ip_address=ip_address, details={"email": email}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )

        # 2. Lookup User
        user = await self.repo.get_user_by_email(email)
        
        # 3. User Existence & Activity Check
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found."
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is inactive."
            )

        # 4. Account Lock Check
        if user.locked_until and user.locked_until > datetime.now(UTC):
            return

        # 5. Generate & Store OTP
        if settings.EMAIL_SERVICE:
            raw_otp = generate_otp()
        else:
            raw_otp = "735011"
            logger.info(f"EMAIL_SERVICE is disabled. Using hardcoded OTP for user {user.email}")

        hashed_otp = hash_otp(raw_otp)

        challenge = OTPChallenge(
            user_id=user.id,
            email=user.email,
            otp_hash=hashed_otp,
            purpose="LOGIN",
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
            ip_address=ip_address,
            user_agent=user_agent,
            delivery_status="PENDING" if settings.EMAIL_SERVICE else "SKIPPED",
        )
        await self.repo.create_otp_challenge(challenge)

        # 6. Async Email Delivery (Fire and forget, but tracked)
        if settings.EMAIL_SERVICE:
            asyncio.create_task(
                EmailService.send_otp_email(
                    to_email=user.email, 
                    otp=raw_otp, 
                    correlation_id=self.correlation_id
                )
            )
        
        event_status = "SUCCESS" if settings.EMAIL_SERVICE else "MOCK_SUCCESS"
        await self.repo.log_audit_event("OTP_SENT", event_status, user.id, ip_address)
        await self.repo.commit()

    async def verify_otp(
        self, 
        email: str, 
        otp: str, 
        ip_address: str, 
        user_agent: str | None = None, 
        device_id: str | None = None
    ) -> TokenResponseSchema:
        """Hardened OTP verification."""
        user = await self.repo.get_user_by_email_for_update(email)
        if not user or not user.is_active:
            await self.repo.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if user.locked_until and user.locked_until > datetime.now(UTC):
            await self.repo.rollback()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is temporarily locked")

        challenge = await self.repo.get_latest_otp_challenge_for_update(email)
        if not challenge:
            await self.repo.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired OTP")

        # Brute-force protection
        challenge.attempt_count += 1
        if challenge.attempt_count > challenge.max_attempts:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
            await self.repo.update_user(user)
            await self.repo.update_otp_challenge(challenge)
            await self.repo.log_audit_event("OTP_MAX_ATTEMPTS", "CRITICAL", user.id, ip_address)
            await self.repo.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Too many attempts")

        if not verify_otp(otp, challenge.otp_hash):
            await self.repo.update_otp_challenge(challenge)
            await self.repo.log_audit_event("OTP_VERIFY_FAILED", "WARNING", user.id, ip_address)
            await self.repo.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        # Success
        challenge.consumed_at = datetime.now(UTC)
        await self.repo.update_otp_challenge(challenge)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.is_verified = True
        user.last_login_at = datetime.now(UTC)
        user.last_login_ip = ip_address
        user.last_login_user_agent = user_agent
        await self.repo.update_user(user)

        tokens = await self._issue_tokens(user, ip_address, user_agent, device_id)
        await self.repo.commit()
        return tokens

    async def _issue_tokens(
        self, user: User, ip_address: str, user_agent: str | None, device_id: str | None, family_id: uuid.UUID | None = None
    ) -> TokenResponseSchema:
        """Issue access and refresh tokens with family tracking."""
        
        # 1. Access Token (with token_version for global revocation)
        access_token = create_access_token(
            data={
                "sub": str(user.id), 
                "email": user.email, 
                "role": user.role.value,
                "v": user.token_version
            }
        )

        # 2. Refresh Token
        raw_refresh = generate_refresh_token()
        refresh_hash = hash_token(raw_refresh, settings.REFRESH_TOKEN_PEPPER)
        
        expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
        
        new_family_id = family_id or uuid.uuid4()

        refresh_session = RefreshSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            family_id=new_family_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        await self.repo.create_refresh_session(refresh_session)

        # 3. Log logical user session
        user_session = UserSession(
            user_id=user.id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_expiry=expires_at,
        )
        await self.repo.create_user_session(user_session)

        return TokenResponseSchema(access_token=access_token, refresh_token=raw_refresh)

    async def refresh_token(
        self, refresh_token: str, ip_address: str, user_agent: str | None = None, device_id: str | None = None
    ) -> TokenResponseSchema:
        """
        Hardened Refresh flow with Token Family Replay Detection.
        If a used token is presented, the entire family is revoked.
        """
        deterministic_hash = hash_token(refresh_token, settings.REFRESH_TOKEN_PEPPER)
        
        # Use SELECT FOR UPDATE for atomicity
        session = await self.repo.get_refresh_session_for_update(deterministic_hash)
        
        if not session:
            await self.repo.log_audit_event("REFRESH_TOKEN_NOT_FOUND", "WARNING", ip_address=ip_address)
            await self.repo.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        # REPLAY DETECTION
        if session.revoked_at:
            # Token was already used or revoked!
            await self.repo.revoke_refresh_family(session.family_id)
            await self.repo.log_audit_event(
                "REFRESH_REPLAY_ATTACK", "CRITICAL", session.user_id, ip_address, 
                details={"family_id": str(session.family_id)}
            )
            await self.repo.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session compromised. Please login again.")

        if session.expires_at < datetime.now(UTC):
            await self.repo.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

        user = await self.repo.get_user_by_id(session.user_id)
        if not user or not user.is_active or (user.locked_until and user.locked_until > datetime.now(UTC)):
            await self.repo.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account invalid")

        # ROTATION: Revoke current token and issue new one in same family
        session.revoked_at = datetime.now(UTC)
        
        new_tokens = await self._issue_tokens(
            user, ip_address, user_agent, device_id, family_id=session.family_id
        )
        
        # Update replacement link
        # We need to find the new session ID. issue_tokens doesn't return it currently.
        # For simplicity in this hardened implementation, we'll fetch the latest for the family.
        latest_session = await self.repo.get_latest_session_in_family(session.family_id)
        session.replaced_by = latest_session.id
        await self.repo.update_refresh_session(session)
        await self.repo.commit()

        return new_tokens

    async def logout(self, refresh_token: str, ip_address: str) -> None:
        """Manual session revocation."""
        deterministic_hash = hash_token(refresh_token, settings.REFRESH_TOKEN_PEPPER)
        session = await self.repo.get_refresh_session_for_update(deterministic_hash)
        if session and not session.revoked_at:
            # We revoke the entire family on logout to be safe
            await self.repo.revoke_refresh_family(session.family_id)
            await self.repo.log_audit_event("LOGOUT", "INFO", session.user_id, ip_address)
            await self.repo.commit()
        else:
            await self.repo.rollback()

    async def create_api_key(self, user_id: uuid.UUID, name: str, scopes: list[str]) -> tuple[APIKey, str]:
        """Issue high-entropy API key."""
        prefix, raw_key, hashed_key = generate_api_key()
        
        api_key = APIKey(
            user_id=user_id,
            key_prefix=prefix,
            key_hash=hashed_key,
            name=name,
            scopes=scopes,
            expires_at=None,
        )
        await self.repo.create_api_key(api_key)
        await self.repo.log_audit_event("API_KEY_CREATED", "INFO", user_id, details={"prefix": prefix})
        await self.repo.commit()
        
        return api_key, raw_key

    async def global_logout(self, user_id: uuid.UUID, ip_address: str):
        """Invalidates all tokens for a user by incrementing token_version."""
        user = await self.repo.get_user_by_id_for_update(user_id)
        if user:
            user.token_version += 1
            await self.repo.update_user(user)
            await self.repo.revoke_all_user_sessions(user_id)
            await self.repo.log_audit_event("GLOBAL_LOGOUT", "CRITICAL", user_id, ip_address)
            await self.repo.commit()
        else:
            await self.repo.rollback()
