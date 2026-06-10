import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import asc, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.auth_models import (
    APIKey,
    AuthAuditLog,
    OTPChallenge,
    RefreshSession,
    User,
    UserRole,
    UserSession,
)


class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def commit(self):
        """Explicitly commit the transaction (Unit of Work)."""
        await self.session.commit()

    async def rollback(self):
        """Explicitly rollback the transaction."""
        await self.session.rollback()

    async def list_users(
        self,
        page: int = 1,
        limit: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> tuple[Sequence[User], int]:
        """
        List users with advanced filtering, fuzzy search, and pagination.
        """
        # 1. Column Mapping
        sort_mapping = {
            "email": User.email,
            "full_name": User.full_name,
            "role": User.role,
            "is_active": User.is_active,
            "created_at": User.created_at,
            "last_login_at": User.last_login_at,
        }

        # 2. Base Query
        query = select(User)

        # 3. Dynamic Filtering
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        # 4. Fuzzy Search
        if search:
            query = query.where(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%"),
                )
            )

        # 5. Sorting
        sort_col = sort_mapping.get(sort_by, User.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        # 6. Pagination & Execution
        # Get total count
        count_stmt = select(func.count()).select_from(query.subquery())
        count_res = await self.session.execute(count_stmt)
        total_records = count_res.scalar() or 0

        # Apply offset and limit
        query = query.offset((page - 1) * limit).limit(limit)
        res = await self.session.execute(query)
        users = res.scalars().all()

        return users, total_records

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalars().first()
        
    async def get_user_by_email_for_update(self, email: str) -> User | None:
        """Fetch user with row-level lock."""
        result = await self.session.execute(select(User).where(User.email == email).with_for_update())
        return result.scalars().first()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()
        
    async def get_user_by_id_for_update(self, user_id: uuid.UUID) -> User | None:
        """Fetch user with row-level lock."""
        result = await self.session.execute(select(User).where(User.id == user_id).with_for_update())
        return result.scalars().first()

    async def create_user(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user(self, user: User) -> User:
        await self.session.flush()
        return user

    async def create_otp_challenge(self, challenge: OTPChallenge) -> OTPChallenge:
        self.session.add(challenge)
        await self.session.flush()
        return challenge

    async def get_latest_otp_challenge(self, email: str, purpose: str = "LOGIN") -> OTPChallenge | None:
        result = await self.session.execute(
            select(OTPChallenge)
            .where(
                OTPChallenge.email == email,
                OTPChallenge.purpose == purpose,
                OTPChallenge.consumed_at.is_(None),
                OTPChallenge.expires_at > datetime.now(UTC),
            )
            .order_by(OTPChallenge.created_at.desc())
        )
        return result.scalars().first()

    async def get_latest_otp_challenge_for_update(self, email: str, purpose: str = "LOGIN") -> OTPChallenge | None:
        """Fetch OTP challenge with row-level lock to prevent double consumption."""
        result = await self.session.execute(
            select(OTPChallenge)
            .where(
                OTPChallenge.email == email,
                OTPChallenge.purpose == purpose,
                OTPChallenge.consumed_at.is_(None),
                OTPChallenge.expires_at > datetime.now(UTC),
            )
            .order_by(OTPChallenge.created_at.desc())
            .with_for_update()
        )
        return result.scalars().first()

    async def update_otp_challenge(self, challenge: OTPChallenge) -> OTPChallenge:
        await self.session.flush()
        return challenge

    async def create_refresh_session(self, session_data: RefreshSession) -> RefreshSession:
        self.session.add(session_data)
        await self.session.flush()
        return session_data

    async def get_refresh_session(self, refresh_token_hash: str) -> RefreshSession | None:
        result = await self.session.execute(
            select(RefreshSession).where(RefreshSession.refresh_token_hash == refresh_token_hash)
        )
        return result.scalars().first()

    async def get_refresh_session_for_update(self, refresh_token_hash: str) -> RefreshSession | None:
        """Fetch a refresh session with a row-level lock for atomic rotation."""
        result = await self.session.execute(
            select(RefreshSession)
            .where(RefreshSession.refresh_token_hash == refresh_token_hash)
            .with_for_update()
        )
        return result.scalars().first()

    async def get_latest_session_in_family(self, family_id: uuid.UUID) -> RefreshSession | None:
        result = await self.session.execute(
            select(RefreshSession)
            .where(RefreshSession.family_id == family_id)
            .order_by(RefreshSession.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def revoke_refresh_family(self, family_id: uuid.UUID) -> None:
        """Revokes an entire token family recursively (Chain Invalidation)."""
        await self.session.execute(
            update(RefreshSession)
            .where(RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def update_refresh_session(self, session_data: RefreshSession) -> RefreshSession:
        await self.session.flush()
        return session_data

    async def create_user_session(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        await self.session.flush()
        return user_session
        
    async def update_user_session(self, user_session: UserSession) -> UserSession:
        await self.session.flush()
        return user_session

    async def create_api_key(self, api_key: APIKey) -> APIKey:
        self.session.add(api_key)
        await self.session.flush()
        return api_key

    async def get_api_key_by_prefix(self, prefix: str) -> APIKey | None:
        result = await self.session.execute(select(APIKey).where(APIKey.key_prefix == prefix))
        return result.scalars().first()

    async def get_user_api_keys(self, user_id: uuid.UUID) -> Sequence[APIKey]:
        result = await self.session.execute(select(APIKey).where(APIKey.user_id == user_id))
        return result.scalars().all()

    async def update_api_key(self, api_key: APIKey) -> APIKey:
        await self.session.flush()
        return api_key

    async def log_audit_event(
        self,
        event_type: str,
        status: str,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        severity: str = "INFO",
        details: dict[str, Any] | None = None,
    ) -> AuthAuditLog:
        log_entry = AuthAuditLog(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            details=details or {},
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def revoke_all_user_sessions(self, user_id: uuid.UUID) -> None:
        """Global logout helper."""
        await self.session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.session_revocation.is_(None))
            .values(session_revocation=datetime.now(UTC))
        )
        await self.session.flush()
