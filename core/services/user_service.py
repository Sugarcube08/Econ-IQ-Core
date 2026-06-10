import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status

from core.models.auth_models import User, UserRole
from core.repositories.auth import AuthRepository
from core.schemas.auth import UserCreateSchema, UserUpdateSchema


class UserService:
    def __init__(self, repo: AuthRepository, correlation_id: str | None = None):
        self.repo = repo
        self.correlation_id = correlation_id

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
        return await self.repo.list_users(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            role=role,
            is_active=is_active,
        )

    async def create_user(self, creator_id: uuid.UUID, user_data: UserCreateSchema) -> User:
        """Create a new user. Only authorized users can call this."""
        existing_user = await self.repo.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        new_user = User(
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=True,
            is_verified=False,  
            created_by_user_id=creator_id,
        )
        
        created_user = await self.repo.create_user(new_user)
        await self.repo.log_audit_event(
            "USER_CREATED", "SUCCESS", creator_id, 
            severity="INFO",
            details={"created_user_id": str(created_user.id)}
        )
        await self.repo.commit()
        return created_user

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def update_user(
        self, 
        user_id: uuid.UUID, 
        update_data: UserUpdateSchema, 
        updater: User
    ) -> User:
        """
        Hardened update logic:
        - Admins can update any user's role and status.
        - Analysts/Viewers can only update THEIR OWN name.
        """
        target_user = await self.get_user(user_id)
        is_admin = updater.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        
        # Security Guard: Self-update or Admin only
        if not is_admin and updater.id != user_id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You can only update your own profile"
            )

        # 1. Profile Details (Allowed for self or admin)
        if update_data.full_name is not None:
            target_user.full_name = update_data.full_name
            
        # 2. Administrative Fields (Admin ONLY)
        if update_data.role is not None or update_data.is_active is not None:
            if not is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Insufficient privileges to change role or account status"
                )
            
            if update_data.role is not None:
                target_user.role = update_data.role
            if update_data.is_active is not None:
                target_user.is_active = update_data.is_active
            
        updated_user = await self.repo.update_user(target_user)
        await self.repo.log_audit_event(
            "USER_UPDATED", "SUCCESS", updater.id, 
            severity="INFO",
            details={"updated_user_id": str(user_id)}
        )
        await self.repo.commit()
        return updated_user

    async def delete_user(self, user_id: uuid.UUID, deleter_id: uuid.UUID) -> None:
        """
        Soft delete a user:
        - Set is_active = False
        - Revoke all active sessions (Global Logout)
        """
        target_user = await self.get_user(user_id)
        
        # 1. Deactivate
        target_user.is_active = False
        await self.repo.update_user(target_user)
        
        # 2. Force Global Logout (Security hardening)
        await self.repo.revoke_all_user_sessions(user_id)
        
        await self.repo.log_audit_event(
            "USER_SOFT_DELETED", "SUCCESS", deleter_id, 
            severity="WARNING",
            details={"deleted_user_id": str(user_id)}
        )
        await self.repo.commit()
