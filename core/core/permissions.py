import enum


class Permission(enum.Enum):
    # User Management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # API Key Management
    API_KEY_CREATE = "api_key:create"
    API_KEY_READ = "api_key:read"
    API_KEY_REVOKE = "api_key:revoke"
    
    # Intelligence Domain
    INTEL_READ = "intelligence:read"
    INTEL_EXPORT = "intelligence:export"
    INTEL_RECOMPUTE = "intelligence:recompute"
    
    # System Admin
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"


# Hierarchical Role Registry
ROLE_PERMISSIONS = {
    "SUPER_ADMIN": set(Permission),
    "ADMIN": {
        Permission.USER_CREATE,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.USER_DELETE,
        Permission.API_KEY_CREATE,
        Permission.API_KEY_READ,
        Permission.API_KEY_REVOKE,
        Permission.INTEL_READ,
        Permission.INTEL_EXPORT,
        Permission.INTEL_RECOMPUTE,
        Permission.SYSTEM_LOGS
    },
    "ANALYST": {
        Permission.INTEL_READ,
        Permission.INTEL_EXPORT,
        Permission.INTEL_RECOMPUTE,
        Permission.USER_READ,
        Permission.USER_UPDATE
    },
    "VIEWER": {
        Permission.INTEL_READ,
        Permission.USER_READ,
        Permission.USER_UPDATE
    },
    "API_ONLY": {
        Permission.INTEL_READ
    }
}

def get_permissions_for_role(role_name: str) -> set[Permission]:
    return ROLE_PERMISSIONS.get(role_name, set())
