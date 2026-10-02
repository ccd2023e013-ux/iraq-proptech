"""Import every model module here so Alembic autogenerate sees all tables."""

from app.audit.models import AuditLog
from app.auth.models import AuthSession, RefreshToken, VerificationToken
from app.db.base import Base
from app.rbac.models import RoleRecord
from app.system.models import SystemSetting
from app.users.models import User, UserRole

__all__ = [
    "AuditLog",
    "AuthSession",
    "Base",
    "RefreshToken",
    "RoleRecord",
    "SystemSetting",
    "User",
    "UserRole",
    "VerificationToken",
]
