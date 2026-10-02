"""Import every model module here so Alembic autogenerate sees all tables."""

from app.agencies.models import Agency, AgencyInvitation, AgencyMember, AgentProfile
from app.audit.models import AuditLog
from app.auth.models import AuthSession, RefreshToken, VerificationToken
from app.db.base import Base
from app.geo.models import City, District, Governorate, Neighborhood
from app.properties.models import (
    Amenity,
    Property,
    PropertyAmenity,
    PropertyDocument,
    PropertyMedia,
    PropertyPriceHistory,
    PropertyStatusHistory,
    PropertyType,
    PropertyVerification,
)
from app.rbac.models import RoleRecord
from app.system.models import SystemSetting
from app.users.models import User, UserRole

__all__ = [
    "Agency",
    "AgencyInvitation",
    "AgencyMember",
    "AgentProfile",
    "Amenity",
    "AuditLog",
    "AuthSession",
    "Base",
    "City",
    "District",
    "Governorate",
    "Neighborhood",
    "Property",
    "PropertyAmenity",
    "PropertyDocument",
    "PropertyMedia",
    "PropertyPriceHistory",
    "PropertyStatusHistory",
    "PropertyType",
    "PropertyVerification",
    "RefreshToken",
    "RoleRecord",
    "SystemSetting",
    "User",
    "UserRole",
    "VerificationToken",
]
