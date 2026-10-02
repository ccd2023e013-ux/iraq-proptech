"""Role-based access control: the single, code-reviewed source of truth.

Roles and their permissions are defined here (versioned with the code and
covered by tests). The database stores *which users hold which roles*
(``user_roles``) and mirrors the role list in ``roles`` for referential
integrity; a test asserts the two never drift apart.

Authorization is always permission-based: endpoints declare the permission
they need (``require_permission(Permission.X)``); resource-level checks
(ownership, agency membership) live in each domain's policy functions.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    MODERATOR = "MODERATOR"
    AGENCY_OWNER = "AGENCY_OWNER"
    AGENT = "AGENT"
    PROPERTY_OWNER = "PROPERTY_OWNER"
    CUSTOMER = "CUSTOMER"


# Higher rank may manage users whose highest role ranks strictly lower.
ROLE_RANK: dict[Role, int] = {
    Role.SUPER_ADMIN: 100,
    Role.ADMIN: 90,
    Role.MODERATOR: 70,
    Role.AGENCY_OWNER: 50,
    Role.AGENT: 40,
    Role.PROPERTY_OWNER: 20,
    Role.CUSTOMER: 10,
}

ROLE_NAMES: dict[Role, tuple[str, str]] = {
    Role.SUPER_ADMIN: ("مدير النظام الأعلى", "Super administrator"),
    Role.ADMIN: ("مدير", "Administrator"),
    Role.MODERATOR: ("مشرف محتوى", "Moderator"),
    Role.AGENCY_OWNER: ("صاحب مكتب عقاري", "Agency owner"),
    Role.AGENT: ("وكيل عقاري", "Agent"),
    Role.PROPERTY_OWNER: ("مالك عقار", "Property owner"),
    Role.CUSTOMER: ("عميل", "Customer"),
}

# Roles a person may pick for themselves at registration.
SELF_SERVICE_ROLES = frozenset({Role.CUSTOMER, Role.PROPERTY_OWNER})


class Permission(StrEnum):
    # Account & administration
    USERS_READ = "users.read"
    USERS_SUSPEND = "users.suspend"
    ROLES_ASSIGN = "roles.assign"
    AUDIT_READ = "audit.read"
    SETTINGS_MANAGE = "settings.manage"

    # Properties
    PROPERTIES_CREATE = "properties.create"
    PROPERTIES_MANAGE_ANY = "properties.manage_any"  # edit/delete anyone's listing
    PROPERTIES_MODERATE = "properties.moderate"  # approve / reject / suspend
    PROPERTIES_VERIFY = "properties.verify"  # record verification evidence
    PROPERTIES_READ_PRIVATE = "properties.read_private"  # unpublished, documents, exact location

    # Agencies & agents
    AGENCIES_CREATE = "agencies.create"
    AGENCIES_MANAGE_ANY = "agencies.manage_any"
    AGENCIES_VERIFY = "agencies.verify"

    # Locations / GIS (districts, neighborhoods, boundaries)
    LOCATIONS_MANAGE = "locations.manage"

    # CRM
    LEADS_READ_OWN = "leads.read_own"
    LEADS_READ_AGENCY = "leads.read_agency"
    LEADS_READ_ANY = "leads.read_any"
    LEADS_MANAGE = "leads.manage"
    LEADS_CONFIGURE = "leads.configure"  # pipeline statuses

    # Buyer features
    INQUIRIES_CREATE = "inquiries.create"
    FAVORITES_MANAGE = "favorites.manage"
    SAVED_SEARCHES_MANAGE = "saved_searches.manage"

    # Trust & safety
    REPORTS_CREATE = "reports.create"
    REPORTS_REVIEW = "reports.review"

    # AI
    AI_USE = "ai.use"
    AI_AUTHOR = "ai.author"  # listing descriptions, lead summaries
    AI_ADMIN = "ai.admin"  # inspect generations, settings

    # Analytics
    ANALYTICS_OWN = "analytics.own"
    ANALYTICS_AGENCY = "analytics.agency"
    ANALYTICS_ALL = "analytics.all"

    # Automation / integrations
    AUTOMATION_MANAGE = "automation.manage"


_BUYER = {
    Permission.AGENCIES_CREATE,  # anyone may apply to open an agency (needs verification)
    Permission.INQUIRIES_CREATE,
    Permission.FAVORITES_MANAGE,
    Permission.SAVED_SEARCHES_MANAGE,
    Permission.REPORTS_CREATE,
    Permission.AI_USE,
}

_LISTER = _BUYER | {
    Permission.PROPERTIES_CREATE,
    Permission.LEADS_READ_OWN,
    Permission.LEADS_MANAGE,
    Permission.AI_AUTHOR,
    Permission.ANALYTICS_OWN,
}

_AGENCY_OWNER = _LISTER | {
    Permission.LEADS_READ_AGENCY,
    Permission.ANALYTICS_AGENCY,
}

_MODERATOR = _BUYER | {
    Permission.USERS_READ,
    Permission.PROPERTIES_MODERATE,
    Permission.PROPERTIES_VERIFY,
    Permission.PROPERTIES_READ_PRIVATE,
    Permission.AGENCIES_VERIFY,
    Permission.REPORTS_REVIEW,
    Permission.AUDIT_READ,
}

_ADMIN = (
    _MODERATOR
    | _AGENCY_OWNER
    | {
        Permission.USERS_SUSPEND,
        Permission.ROLES_ASSIGN,
        Permission.PROPERTIES_MANAGE_ANY,
        Permission.AGENCIES_MANAGE_ANY,
        Permission.LEADS_READ_ANY,
        Permission.LEADS_CONFIGURE,
        Permission.AI_ADMIN,
        Permission.ANALYTICS_ALL,
        Permission.AUTOMATION_MANAGE,
        Permission.LOCATIONS_MANAGE,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SUPER_ADMIN: frozenset(Permission),
    Role.ADMIN: frozenset(_ADMIN),
    Role.MODERATOR: frozenset(_MODERATOR),
    Role.AGENCY_OWNER: frozenset(_AGENCY_OWNER),
    Role.AGENT: frozenset(_LISTER),
    Role.PROPERTY_OWNER: frozenset(_LISTER),
    Role.CUSTOMER: frozenset(_BUYER),
}

# Settings changes stay with super admins only.
assert Permission.SETTINGS_MANAGE not in ROLE_PERMISSIONS[Role.ADMIN]  # noqa: S101


def permissions_for(roles: set[Role] | frozenset[Role]) -> frozenset[Permission]:
    result: set[Permission] = set()
    for role in roles:
        result |= ROLE_PERMISSIONS[role]
    return frozenset(result)


def highest_rank(roles: set[Role] | frozenset[Role]) -> int:
    return max((ROLE_RANK[r] for r in roles), default=0)


def can_manage(actor_roles: frozenset[Role], target_roles: frozenset[Role]) -> bool:
    """An actor may act on another user only if they strictly outrank them."""
    return highest_rank(actor_roles) > highest_rank(target_roles)


def can_grant(actor_roles: frozenset[Role], role: Role) -> bool:
    """Roles can only be granted below one's own rank (SUPER_ADMIN only via CLI)."""
    return highest_rank(actor_roles) > ROLE_RANK[role]
