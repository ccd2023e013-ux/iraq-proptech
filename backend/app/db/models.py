"""Import every model module here so Alembic autogenerate sees all tables."""

from app.db.base import Base
from app.system.models import SystemSetting

__all__ = ["Base", "SystemSetting"]
