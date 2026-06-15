import argparse
import asyncio
import re
import sys
from pathlib import Path

# Ensure project root is in python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger  # noqa: E402

from core.models.auth_models import User, UserRole  # noqa: E402
from core.repositories.auth import AuthRepository  # noqa: E402
from core.storage.postgres import AsyncSessionLocal, Base, engine  # noqa: E402


def validate_email(email: str) -> bool:
    """Validate email address format."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))


async def create_superuser(email: str | None, name: str | None, promote: bool = False):
    """
    Creates a new superuser (SUPER_ADMIN) or promotes an existing user.
    """
    print("=" * 60)
    print("                 ECONIQ SUPERUSER MANAGER (OTP-ONLY)")
    print("=" * 60)

    # 1. Prompt/validate email
    if not email:
        while True:
            email = input("Enter Email Address: ").strip()
            if not email:
                print("Email address cannot be empty.")
                continue
            if not validate_email(email):
                print("Invalid email format. Please enter a valid email address.")
                continue
            break
    else:
        if not validate_email(email):
            print(f"Error: Invalid email format: '{email}'")
            sys.exit(1)

    # 2. Prompt/validate name (not needed if just promoting, unless updating name)
    if not name and not promote:
        while True:
            name = input("Enter Full Name: ").strip()
            if not name:
                print("Full name cannot be empty.")
                continue
            break

    # 3. Verify/create database schema before querying/inserting
    print("Verifying database schema (creating tables if not exist)...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database schema verified.")
    except Exception as schema_err:
        print(f"[WARNING] Schema verification failed (continuing anyway): {schema_err}")

    # 4. Create database records
    async with AsyncSessionLocal() as session:
        repo = AuthRepository(session)
        
        try:
            # Check if user already exists
            existing_user = await repo.get_user_by_email_for_update(email)
            
            if existing_user:
                if promote:
                    print(f"\nUser '{email}' found. Promoting to SUPER_ADMIN...")
                    existing_user.role = UserRole.SUPER_ADMIN
                    existing_user.is_active = True
                    existing_user.is_verified = True
                    if name:
                        existing_user.full_name = name
                    
                    await repo.update_user(existing_user)
                    await repo.log_audit_event(
                        event_type="SUPERUSER_PROMOTED",
                        status="SUCCESS",
                        user_id=existing_user.id,
                        severity="WARNING",
                        details={"email": email}
                    )
                    await repo.commit()
                    print(f"\n[SUCCESS] User '{email}' promoted to SUPER_ADMIN successfully!")
                else:
                    print(f"\nError: User with email '{email}' already exists.")
                    print("To promote this user to superuser, run this script with the --promote flag.")
                    sys.exit(1)
            else:
                if promote:
                    print(f"\nError: User '{email}' does not exist. Cannot promote.")
                    print("Run without the --promote flag to create a new superuser.")
                    sys.exit(1)
                
                print(f"\nCreating new SUPER_ADMIN user: {email}...")
                
                new_user = User(
                    email=email,
                    full_name=name,
                    role=UserRole.SUPER_ADMIN,
                    is_active=True,
                    is_verified=True
                )
                
                created_user = await repo.create_user(new_user)
                await repo.log_audit_event(
                    event_type="SUPERUSER_CREATED",
                    status="SUCCESS",
                    user_id=created_user.id,
                    severity="WARNING",
                    details={"email": email}
                )
                await repo.commit()
                print(f"\n[SUCCESS] Superuser '{email}' created successfully!")
                
        except Exception as e:
            await repo.rollback()
            print(f"\n[ERROR] Database transaction failed: {e}")
            logger.error(f"Failed to create/promote superuser: {e}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Create or promote a superuser in Econiq Core (OTP-only).")
    parser.add_argument("--email", type=str, help="Email address of the superuser.")
    parser.add_argument("--name", type=str, help="Full name of the superuser.")
    parser.add_argument("--promote", action="store_true", help="Promote an existing user to superuser.")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(create_superuser(
            email=args.email,
            name=args.name,
            promote=args.promote
        ))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
