"""Import every model module here so Alembic autogenerate sees all tables."""

from app.agencies.models import Agency, AgencyInvitation, AgencyMember, AgentProfile
from app.ai.models import AIGeneration
from app.analytics.models import PropertyViewDaily, PropertyViewVisitor, SearchStatDaily
from app.audit.models import AuditLog
from app.auth.models import AuthSession, RefreshToken, VerificationToken
from app.billing.models import Payment, Plan, Promotion, Subscription
from app.crm.models import (
    Appointment,
    Conversation,
    CrmTask,
    Customer,
    Inquiry,
    Lead,
    LeadActivity,
    LeadStatus,
    Message,
)
from app.db.base import Base
from app.favorites import Favorite
from app.geo.models import City, District, Governorate, Neighborhood
from app.geo.pois import PointOfInterest
from app.moderation.models import ErrorEvent, Report
from app.money import ExchangeRate
from app.notifications.models import (
    JobRun,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    PushSubscription,
    WebhookDelivery,
    WebhookEndpoint,
)
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
    "AIGeneration",
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
    "Conversation",
    "CrmTask",
    "Customer",
    "District",
    "ErrorEvent",
    "ExchangeRate",
    "Favorite",
    "Governorate",
    "Inquiry",
    "JobRun",
    "Lead",
    "LeadActivity",
    "LeadStatus",
    "Message",
    "Neighborhood",
    "Notification",
    "NotificationDelivery",
    "NotificationPreference",
    "Payment",
    "Plan",
    "PointOfInterest",
    "Promotion",
    "Property",
    "PropertyAmenity",
    "PropertyDocument",
    "PropertyMedia",
    "PropertyPriceHistory",
    "PropertyStatusHistory",
    "PropertyType",
    "PropertyVerification",
    "PropertyViewDaily",
    "PropertyViewVisitor",
    "PushSubscription",
    "RefreshToken",
    "Report",
    "RoleRecord",
    "SavedSearch",
    "SearchStatDaily",
    "Subscription",
    "SystemSetting",
    "User",
    "UserRole",
    "VerificationToken",
    "WebhookDelivery",
    "WebhookEndpoint",
]
