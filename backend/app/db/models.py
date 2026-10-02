"""Import every model module here so Alembic autogenerate sees all tables."""

from app.agencies.models import Agency, AgencyInvitation, AgencyMember, AgentProfile
from app.audit.models import AuditLog
from app.auth.models import AuthSession, RefreshToken, VerificationToken
from app.crm.models import (
    Appointment,
    CrmTask,
    Customer,
    Inquiry,
    Lead,
    LeadActivity,
    LeadStatus,
)
from app.db.base import Base
from app.favorites import Favorite
from app.geo.models import City, District, Governorate, Neighborhood
from app.geo.pois import PointOfInterest
from app.money import ExchangeRate
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
from app.search.saved import SavedSearch
from app.system.models import SystemSetting
from app.users.models import User, UserRole

__all__ = [
    "Agency",
    "AgencyInvitation",
    "AgencyMember",
    "AgentProfile",
    "Amenity",
    "Appointment",
    "AuditLog",
    "AuthSession",
    "Base",
    "City",
    "CrmTask",
    "Customer",
    "District",
    "ExchangeRate",
    "Favorite",
    "Governorate",
    "Inquiry",
    "Lead",
    "LeadActivity",
    "LeadStatus",
    "Neighborhood",
    "PointOfInterest",
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
    "SavedSearch",
    "SystemSetting",
    "User",
    "UserRole",
    "VerificationToken",
]
