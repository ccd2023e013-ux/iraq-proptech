"""Property (listing) use cases: CRUD, lifecycle, moderation, verification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import events
from app.agencies.models import Agency, AgencyStatus, MemberRole
from app.audit import service as audit
from app.auth.deps import Principal
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.geo.models import City, District, Governorate, Neighborhood
from app.geo.spatial import coarsen, make_point, point_lonlat
from app.policies import can_manage_property, membership
from app.properties.enums import (
    LocationPrivacy,
    MediaKind,
    PropertyStatus,
    Purpose,
    VerificationKind,
    VerificationResult,
)
from app.properties.models import (
    Amenity,
    Property,
    PropertyAmenity,
    PropertyPriceHistory,
    PropertyStatusHistory,
    PropertyType,
    PropertyVerification,
)
from app.properties.schemas import (
    GeoPoint,
    PropertyCreate,
    PropertyUpdate,
    VerificationIn,
    check_price_rules,
)
from app.rbac.catalog import Permission
from app.system.settings_service import get_setting

# Verification kinds that, when PASSED, earn the public "verified" badge.
BADGE_KINDS = {VerificationKind.OWNERSHIP, VerificationKind.DOCUMENT, VerificationKind.SITE_VISIT}
SOLD_PURPOSES = {Purpose.SALE, Purpose.EXCHANGE}


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- lookups


def get_property_or_404(db: Session, property_id: uuid.UUID, *, lock: bool = False) -> Property:
    prop = db.get(Property, property_id, with_for_update=lock)
    if prop is None or prop.deleted_at is not None:
        raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
    return prop


def manages(db: Session, principal: Principal, prop: Property) -> bool:
    return can_manage_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    )


def ensure_manage(db: Session, principal: Principal, prop: Property) -> None:
    if not manages(db, principal, prop):
        # Unpublished listings stay invisible; published ones exist but are not yours.
        if not prop.is_public and not principal.has(Permission.PROPERTIES_READ_PRIVATE):
            raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
        raise PermissionDeniedError("You cannot modify this listing")


# --------------------------------------------------------------------------- validation


def _validate_location(
    db: Session,
    governorate_id: uuid.UUID,
    city_id: uuid.UUID,
    district_id: uuid.UUID | None,
    neighborhood_id: uuid.UUID | None,
) -> Neighborhood | None:
    def fail(field: str) -> AppError:
        return AppError("Location fields do not match", code="INVALID_LOCATION", details=[field])

    gov = db.get(Governorate, governorate_id)
    city = db.get(City, city_id)
    if gov is None or not gov.is_active:
        raise fail("governorate_id")
    if city is None or not city.is_active or city.governorate_id != gov.id:
        raise fail("city_id")
    district = db.get(District, district_id) if district_id else None
    if district_id and (district is None or district.city_id != city.id):
        raise fail("district_id")
    neighborhood = db.get(Neighborhood, neighborhood_id) if neighborhood_id else None
    if neighborhood_id and (
        neighborhood is None or district is None or neighborhood.district_id != district.id
    ):
        raise fail("neighborhood_id")
    return neighborhood


def _validate_type(db: Session, code: str) -> None:
    ptype = db.get(PropertyType, code)
    if ptype is None or not ptype.is_active:
        raise AppError("Unknown property type", code="INVALID_PROPERTY_TYPE")


def _validate_amenities(db: Session, codes: list[str]) -> None:
    if not codes:
        return
    known = set(
        db.execute(
            select(Amenity.code).where(Amenity.code.in_(codes), Amenity.is_active.is_(True))
        ).scalars()
    )
    unknown = sorted(set(codes) - known)
    if unknown:
        raise AppError("Unknown amenities", code="INVALID_AMENITY", details=unknown)


def _display_location(
    location: GeoPoint | None, privacy: str, neighborhood: Neighborhood | None
) -> Any | None:
    """Public point derived from the exact one; never more precise than allowed."""
    if location is None or privacy == LocationPrivacy.HIDDEN:
        return None
    if privacy == LocationPrivacy.EXACT:
        return make_point(location.lon, location.lat)
    centre = point_lonlat(neighborhood.centroid) if neighborhood is not None else None
    lon, lat = centre if centre else coarsen(location.lon, location.lat)
    return make_point(lon, lat)


def _resolve_agency(
    db: Session, principal: Principal, requested_agent_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """(agency_id, agent_id) for a new listing created by ``principal``."""
    m = membership(db, principal.id)
    if m is None:
        if requested_agent_id not in (None, principal.id):
            raise AppError("Only agency owners can assign agents", code="INVALID_AGENT")
        return None, None
    agency = db.get(Agency, m.agency_id)
    if agency is None or agency.status in (AgencyStatus.SUSPENDED, AgencyStatus.REJECTED):
        raise PermissionDeniedError("Your agency cannot publish listings", code="AGENCY_INACTIVE")
    if m.role == MemberRole.AGENT:
        if requested_agent_id not in (None, principal.id):
            raise AppError("Agents can only assign themselves", code="INVALID_AGENT")
        return agency.id, principal.id
    return agency.id, _validated_agent(db, agency.id, requested_agent_id)


def _validated_agent(
    db: Session, agency_id: uuid.UUID, agent_id: uuid.UUID | None
) -> uuid.UUID | None:
    if agent_id is None:
        return None
    m = membership(db, agent_id)
    if m is None or m.agency_id != agency_id:
        raise AppError("The agent must belong to the same agency", code="INVALID_AGENT")
    return agent_id


def _next_reference(db: Session, governorate: Governorate) -> str:
    seq = db.execute(text("SELECT nextval('property_reference_seq')")).scalar_one()
    return f"{governorate.code}-{seq:07d}"


def _record_status(
    db: Session,
    prop: Property,
    to: PropertyStatus,
    actor: uuid.UUID | None,
    reason: str | None,
    reason_code: str | None = None,
) -> None:
    db.add(
        PropertyStatusHistory(
            property_id=prop.id,
            from_status=None if prop.status is None else str(prop.status),
            to_status=to.value,
            reason=reason,
            reason_code=reason_code,
            changed_by_id=actor,
            # Explicit wall-clock time (not transaction time) keeps ordering exact.
            changed_at=_now(),
        )
    )
    prop.status = to.value
    prop.status_reason = reason
    prop.status_reason_code = reason_code


def _record_price(db: Session, prop: Property, actor: uuid.UUID) -> None:
    db.add(
        PropertyPriceHistory(
            property_id=prop.id,
            price_amount=prop.price_amount,
            currency=prop.currency,
            price_on_request=prop.price_on_request,
            changed_by_id=actor,
            changed_at=_now(),
        )
    )


# --------------------------------------------------------------------------- create / update


def create_property(db: Session, principal: Principal, data: PropertyCreate) -> Property:
    neighborhood = _validate_location(
        db, data.governorate_id, data.city_id, data.district_id, data.neighborhood_id
    )
    _validate_type(db, data.property_type_code)
    _validate_amenities(db, data.amenities)
    agency_id, agent_id = _resolve_agency(db, principal, data.agent_id)
    governorate = db.get(Governorate, data.governorate_id)
    assert governorate is not None  # noqa: S101 - validated above

    fields = data.model_dump(
        mode="python", exclude={"amenities", "location", "agent_id", "virtual_tour_url"}
    )
    prop = Property(
        id=uuid.uuid4(),
        **fields,
        virtual_tour_url=str(data.virtual_tour_url) if data.virtual_tour_url else None,
        reference_code=_next_reference(db, governorate),
        location=make_point(data.location.lon, data.location.lat) if data.location else None,
        display_location=_display_location(data.location, data.location_privacy, neighborhood),
        lister_id=principal.id,
        agency_id=agency_id,
        agent_id=agent_id,
        status=None,
    )
    prop.amenity_links = [PropertyAmenity(amenity_code=c) for c in data.amenities]
    db.add(prop)
    _record_status(db, prop, PropertyStatus.DRAFT, principal.id, None)
    db.flush()
    _record_price(db, prop, principal.id)
    audit.record(
        db,
        "property.created",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"reference": prop.reference_code},
    )
    db.commit()
    return prop


_PRICE_FIELDS = {"price_amount", "currency", "price_on_request"}
_LOCATION_FIELDS = {"governorate_id", "city_id", "district_id", "neighborhood_id"}


def update_property(
    db: Session, principal: Principal, prop: Property, data: PropertyUpdate
) -> Property:
    ensure_manage(db, principal, prop)
    if prop.status in (PropertyStatus.SUSPENDED,) and not principal.has(
        Permission.PROPERTIES_MODERATE
    ):
        raise PermissionDeniedError("Suspended listings cannot be edited", code="LISTING_LOCKED")
    changes = data.model_dump(exclude_unset=True, mode="python")
    if not changes:
        return prop

    merged: dict[str, Any] = {
        "purpose": changes.get("purpose", prop.purpose),
        "rent_period": changes.get("rent_period", prop.rent_period),
        "price_amount": changes.get("price_amount", prop.price_amount),
        "price_on_request": changes.get("price_on_request", prop.price_on_request),
    }
    try:
        check_price_rules(**merged)
    except ValueError as exc:
        raise AppError(str(exc), code="VALIDATION_ERROR") from exc

    if "property_type_code" in changes:
        _validate_type(db, changes["property_type_code"])
    if "amenities" in changes:
        codes = sorted(set(changes.pop("amenities") or []))
        _validate_amenities(db, codes)
        prop.amenity_links = [PropertyAmenity(amenity_code=c) for c in codes]

    location_touched = bool((_LOCATION_FIELDS | {"location", "location_privacy"}) & changes.keys())
    neighborhood = None
    if location_touched:
        neighborhood = _validate_location(
            db,
            changes.get("governorate_id", prop.governorate_id),
            changes.get("city_id", prop.city_id),
            changes.get("district_id", prop.district_id),
            changes.get("neighborhood_id", prop.neighborhood_id),
        )

    if "agent_id" in changes:
        agent_id = changes.pop("agent_id")
        if prop.agency_id is None:
            if agent_id not in (None, prop.lister_id):
                raise AppError("Only agency listings have assigned agents", code="INVALID_AGENT")
        else:
            m = membership(db, principal.id)
            is_owner = m is not None and m.role == MemberRole.OWNER
            if not (is_owner or principal.has(Permission.PROPERTIES_MANAGE_ANY)):
                raise PermissionDeniedError("Only the agency owner can reassign agents")
            prop.agent_id = _validated_agent(db, prop.agency_id, agent_id)

    new_location = changes.pop("location", None) if "location" in changes else None
    location_cleared = "location" in data.model_fields_set and data.location is None
    if "virtual_tour_url" in changes:
        url = changes.pop("virtual_tour_url")
        prop.virtual_tour_url = str(url) if url else None

    price_changed = any(k in changes and changes[k] != getattr(prop, k) for k in _PRICE_FIELDS)
    for key, value in changes.items():
        setattr(prop, key, value)

    if location_touched:
        if new_location is not None:
            point = GeoPoint(**new_location) if isinstance(new_location, dict) else new_location
            prop.location = make_point(point.lon, point.lat)
        elif location_cleared:
            prop.location = None
        current = point_lonlat(prop.location)
        geo = GeoPoint(lon=current[0], lat=current[1]) if current else None
        prop.display_location = _display_location(geo, prop.location_privacy, neighborhood)

    if price_changed:
        _record_price(db, prop, principal.id)
    if prop.status == PropertyStatus.APPROVED and not principal.has(Permission.PROPERTIES_MODERATE):
        prop.needs_review = True  # live listing changed: flag for moderators
    audit.record(
        db,
        "property.updated",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"fields": ",".join(sorted(data.model_fields_set))},
    )
    db.commit()
    return prop


def delete_property(db: Session, principal: Principal, prop: Property) -> None:
    ensure_manage(db, principal, prop)
    prop.deleted_at = _now()
    audit.record(
        db, "property.deleted", actor_id=principal.id, resource_type="property", resource_id=prop.id
    )
    db.commit()


# --------------------------------------------------------------------------- lifecycle

_OWNER_TRANSITIONS: dict[str, tuple[set[PropertyStatus], PropertyStatus]] = {
    "submit": (
        {PropertyStatus.DRAFT, PropertyStatus.REJECTED, PropertyStatus.EXPIRED},
        PropertyStatus.PENDING_REVIEW,
    ),
    "unpublish": ({PropertyStatus.APPROVED, PropertyStatus.PENDING_REVIEW}, PropertyStatus.DRAFT),
    "archive": (
        {
            PropertyStatus.DRAFT,
            PropertyStatus.APPROVED,
            PropertyStatus.PENDING_REVIEW,
            PropertyStatus.REJECTED,
            PropertyStatus.SOLD,
            PropertyStatus.RENTED,
            PropertyStatus.EXPIRED,
        },
        PropertyStatus.ARCHIVED,
    ),
    "mark_sold": ({PropertyStatus.APPROVED}, PropertyStatus.SOLD),
    "mark_rented": ({PropertyStatus.APPROVED}, PropertyStatus.RENTED),
}


def submission_problems(prop: Property) -> list[str]:
    problems = []
    if not any(m.kind == MediaKind.IMAGE and m.moderation == "APPROVED" for m in prop.media):
        problems.append("NO_IMAGES")
    if not prop.description_ar or len(prop.description_ar.strip()) < 20:
        problems.append("DESCRIPTION_TOO_SHORT")
    return problems


def _auto_approvable(db: Session, prop: Property) -> bool:
    if prop.agency_id is None or not get_setting(db, "listings.auto_approve_verified_agencies"):
        return False
    agency = db.get(Agency, prop.agency_id)
    return agency is not None and agency.status == AgencyStatus.VERIFIED


def owner_transition(
    db: Session, principal: Principal, prop: Property, action: str, reason: str | None
) -> Property:
    ensure_manage(db, principal, prop)
    allowed_from, target = _OWNER_TRANSITIONS[action]
    if PropertyStatus(prop.status) not in allowed_from:
        raise AppError(
            f"Cannot {action} a listing in status {prop.status}",
            code="INVALID_TRANSITION",
            status_code=409,
        )
    if action == "submit":
        if not principal.user.email_verified:
            raise PermissionDeniedError("Verify your email first", code="EMAIL_NOT_VERIFIED")
        problems = submission_problems(prop)
        if problems:
            raise AppError("Listing is incomplete", code="SUBMISSION_INCOMPLETE", details=problems)
    if action == "mark_sold" and prop.purpose not in SOLD_PURPOSES:
        raise AppError(
            "Only sale listings can be marked sold", code="INVALID_TRANSITION", status_code=409
        )
    if action == "mark_rented" and prop.purpose in SOLD_PURPOSES:
        raise AppError(
            "Only rental listings can be marked rented", code="INVALID_TRANSITION", status_code=409
        )
    _record_status(db, prop, target, principal.id, reason)
    if action == "submit" and _auto_approvable(db, prop):
        _record_status(db, prop, PropertyStatus.APPROVED, None, "auto-approved: verified agency")
        now = _now()
        prop.published_at = prop.published_at or now
        prop.expires_at = now + timedelta(days=get_setting(db, "listings.lifetime_days"))
        prop.needs_review = False
    audit.record(
        db,
        f"property.{action}",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"to": target.value},
    )
    db.commit()
    return prop


_MODERATION: dict[str, tuple[set[PropertyStatus], PropertyStatus, bool]] = {
    # decision: (allowed from, target, reason required)
    "APPROVE": ({PropertyStatus.PENDING_REVIEW}, PropertyStatus.APPROVED, False),
    "REJECT": ({PropertyStatus.PENDING_REVIEW}, PropertyStatus.REJECTED, True),
    "SUSPEND": (
        {PropertyStatus.APPROVED, PropertyStatus.PENDING_REVIEW},
        PropertyStatus.SUSPENDED,
        True,
    ),
    "REINSTATE": ({PropertyStatus.SUSPENDED}, PropertyStatus.APPROVED, False),
}


def moderate(
    db: Session,
    principal: Principal,
    prop: Property,
    decision: str,
    reason: str | None,
    reason_code: str | None = None,
) -> Property:
    allowed_from, target, needs_reason = _MODERATION[decision]
    m = membership(db, principal.id)
    own_agency = m is not None and prop.agency_id is not None and m.agency_id == prop.agency_id
    if principal.id in (prop.lister_id, prop.agent_id) or own_agency:
        raise PermissionDeniedError(
            "You cannot moderate your own listing", code="CONFLICT_OF_INTEREST"
        )
    if PropertyStatus(prop.status) not in allowed_from:
        raise AppError(
            f"Cannot {decision.lower()} a listing in status {prop.status}",
            code="INVALID_TRANSITION",
            status_code=409,
        )
    if needs_reason and not (reason and reason.strip()):
        raise AppError("A reason is required", code="REASON_REQUIRED")
    if needs_reason and reason_code is None:
        reason_code = "OTHER"
    _record_status(db, prop, target, principal.id, reason, reason_code if needs_reason else None)
    if target == PropertyStatus.APPROVED:
        now = _now()
        prop.published_at = prop.published_at or now
        prop.expires_at = now + timedelta(days=get_setting(db, "listings.lifetime_days"))
        prop.needs_review = False
    audit.record(
        db,
        f"property.moderation.{decision.lower()}",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"to": target.value, "reason": reason, "reason_code": reason_code},
    )
    events.emit(
        db,
        f"property.{target.value.lower()}",
        {
            "property_id": str(prop.id),
            "lister_id": str(prop.lister_id),
            "agent_id": str(prop.agent_id) if prop.agent_id else None,
            "decision": decision,
            "reason_code": reason_code,
        },
    )
    db.commit()
    return prop


def add_verification(
    db: Session, principal: Principal, prop: Property, data: VerificationIn
) -> PropertyVerification:
    record = PropertyVerification(
        property_id=prop.id,
        kind=data.kind.value,
        result=data.result.value,
        note=data.note,
        document_id=data.document_id,
        verified_by_id=principal.id,
    )
    db.add(record)
    if data.result == VerificationResult.PASSED and data.kind in BADGE_KINDS:
        prop.verified_at = prop.verified_at or _now()
    audit.record(
        db,
        "property.verification_recorded",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"kind": data.kind.value, "result": data.result.value},
    )
    db.commit()
    return record


# --------------------------------------------------------------------------- listing queries


def list_public(db: Session, *, offset: int, limit: int) -> tuple[list[Property], int]:
    stmt = select(Property).where(
        Property.status == PropertyStatus.APPROVED, Property.deleted_at.is_(None)
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Property.published_at.desc(), Property.id).offset(offset).limit(limit)
    ).scalars()
    return list(rows), total


def list_managed(
    db: Session, principal: Principal, *, status: str | None, offset: int, limit: int
) -> tuple[list[Property], int]:
    """Listings the caller manages: own, assigned, or (for owners) the agency's."""
    m = membership(db, principal.id)
    stmt = select(Property).where(Property.deleted_at.is_(None))
    if m is not None and m.role == MemberRole.OWNER:
        stmt = stmt.where(
            (Property.agency_id == m.agency_id)
            | ((Property.lister_id == principal.id) & Property.agency_id.is_(None))
        )
    elif m is not None:
        stmt = stmt.where(
            (Property.agency_id == m.agency_id)
            & ((Property.lister_id == principal.id) | (Property.agent_id == principal.id))
            | ((Property.lister_id == principal.id) & Property.agency_id.is_(None))
        )
    else:
        stmt = stmt.where(Property.lister_id == principal.id, Property.agency_id.is_(None))
    if status:
        stmt = stmt.where(Property.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Property.updated_at.desc(), Property.id).offset(offset).limit(limit)
    ).scalars()
    return list(rows), total


def price_history(db: Session, prop: Property) -> list[PropertyPriceHistory]:
    return list(
        db.execute(
            select(PropertyPriceHistory)
            .where(PropertyPriceHistory.property_id == prop.id)
            .order_by(PropertyPriceHistory.changed_at, PropertyPriceHistory.id)
        ).scalars()
    )


def status_history(db: Session, prop: Property) -> list[PropertyStatusHistory]:
    return list(
        db.execute(
            select(PropertyStatusHistory)
            .where(PropertyStatusHistory.property_id == prop.id)
            .order_by(PropertyStatusHistory.changed_at, PropertyStatusHistory.id)
        ).scalars()
    )
