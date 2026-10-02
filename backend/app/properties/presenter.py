"""Turn Property rows into API representations without N+1 queries.

All related rows a page needs (places, agencies, agent profiles, listers)
are fetched in a handful of batched ``IN`` queries per page.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agencies.models import Agency, AgencyStatus, AgentProfile
from app.auth.deps import Principal
from app.geo.models import City, District, Governorate, Neighborhood
from app.geo.spatial import point_lonlat
from app.policies import can_manage_property, can_view_private_property
from app.properties.enums import MediaKind, ModerationState
from app.properties.media_service import media_url
from app.properties.models import Property, PropertyMedia
from app.properties.schemas import (
    LatLon,
    ListerOut,
    MediaOut,
    PlaceRef,
    PropertyCard,
    PropertyOut,
)
from app.users.models import User


def _latlon(value: Any) -> LatLon | None:
    pair = point_lonlat(value)
    return LatLon(lon=pair[0], lat=pair[1]) if pair else None


def _ref(place: Any | None) -> PlaceRef | None:
    return PlaceRef(id=place.id, name_ar=place.name_ar, name_en=place.name_en) if place else None


def _fetch(db: Session, model: Any, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, Any]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {row.id: row for row in db.execute(select(model).where(model.id.in_(wanted))).scalars()}


@dataclass
class _Context:
    governorates: dict[uuid.UUID, Governorate] = field(default_factory=dict)
    cities: dict[uuid.UUID, City] = field(default_factory=dict)
    districts: dict[uuid.UUID, District] = field(default_factory=dict)
    neighborhoods: dict[uuid.UUID, Neighborhood] = field(default_factory=dict)
    agencies: dict[uuid.UUID, Agency] = field(default_factory=dict)
    users: dict[uuid.UUID, User] = field(default_factory=dict)
    profiles: dict[uuid.UUID, AgentProfile] = field(default_factory=dict)


def _context(db: Session, props: Sequence[Property], *, with_people: bool) -> _Context:
    ctx = _Context(
        governorates=_fetch(db, Governorate, (p.governorate_id for p in props)),
        cities=_fetch(db, City, (p.city_id for p in props)),
        districts=_fetch(db, District, (p.district_id for p in props)),
        neighborhoods=_fetch(db, Neighborhood, (p.neighborhood_id for p in props)),
        agencies=_fetch(db, Agency, (p.agency_id for p in props)),
    )
    if with_people:
        people = {p.lister_id for p in props} | {p.agent_id for p in props if p.agent_id}
        ctx.users = _fetch(db, User, people)
        ctx.profiles = {
            row.user_id: row
            for row in db.execute(
                select(AgentProfile).where(AgentProfile.user_id.in_(people))
            ).scalars()
        }
    return ctx


def _visible_media(prop: Property, include_hidden: bool) -> list[PropertyMedia]:
    return [m for m in prop.media if include_hidden or m.moderation == ModerationState.APPROVED]


def _media_out(media: PropertyMedia) -> MediaOut:
    out = MediaOut.model_validate(media)
    out.url = media_url(media)
    out.thumbnail_url = media_url(media, thumbnail=True) if media.thumbnail_key else None
    return out


def _cover(prop: Property) -> str | None:
    for media in prop.media:
        if media.kind == MediaKind.IMAGE and media.moderation == ModerationState.APPROVED:
            return media_url(media, thumbnail=True)
    return None


def _lister(prop: Property, ctx: _Context) -> ListerOut:
    agency = ctx.agencies.get(prop.agency_id) if prop.agency_id else None
    agent_profile = ctx.profiles.get(prop.agent_id) if prop.agent_id else None
    lister = ctx.users.get(prop.lister_id)
    if agency is not None:
        return ListerOut(
            kind="agency",
            name=agent_profile.display_name if agent_profile else agency.name_ar,
            agency_id=agency.id,
            agent_id=prop.agent_id,
            phone=(agent_profile.public_phone if agent_profile else None) or agency.phone
            if prop.show_phone
            else None,
            whatsapp=(agent_profile.whatsapp if agent_profile else None) or agency.whatsapp
            if prop.allow_whatsapp
            else None,
            agency_verified=agency.status == AgencyStatus.VERIFIED,
        )
    own_profile = ctx.profiles.get(prop.lister_id)
    if own_profile is not None:
        return ListerOut(
            kind="agent",
            name=own_profile.display_name,
            agent_id=prop.lister_id,
            phone=(own_profile.public_phone or (lister.phone if lister else None))
            if prop.show_phone
            else None,
            whatsapp=own_profile.whatsapp if prop.allow_whatsapp else None,
        )
    # Private owner: first name only; phone only with explicit consent.
    first_name = (lister.full_name.split()[0] if lister and lister.full_name else "") or "—"
    phone = lister.phone if (lister and prop.show_phone) else None
    return ListerOut(
        kind="owner",
        name=first_name,
        phone=phone,
        whatsapp=phone if prop.allow_whatsapp else None,
    )


def to_out(db: Session, prop: Property, principal: Principal | None) -> PropertyOut:
    ctx = _context(db, [prop], with_people=True)
    private = can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    )
    can_edit = principal is not None and can_manage_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    )
    out = PropertyOut(
        id=prop.id,
        reference_code=prop.reference_code,
        title_ar=prop.title_ar,
        title_en=prop.title_en,
        description_ar=prop.description_ar,
        description_en=prop.description_en,
        property_type_code=prop.property_type_code,
        purpose=prop.purpose,
        rent_period=prop.rent_period,
        price_amount=prop.price_amount,
        currency=prop.currency,
        price_on_request=prop.price_on_request,
        negotiable=prop.negotiable,
        area_m2=prop.area_m2,
        land_area_m2=prop.land_area_m2,
        bedrooms=prop.bedrooms,
        bathrooms=prop.bathrooms,
        floors=prop.floors,
        floor_number=prop.floor_number,
        year_built=prop.year_built,
        condition=prop.condition,
        furnishing=prop.furnishing,
        ownership_document=prop.ownership_document,
        amenities=prop.amenity_codes,
        governorate=_ref(ctx.governorates[prop.governorate_id]),
        city=_ref(ctx.cities[prop.city_id]),
        district=_ref(ctx.districts.get(prop.district_id)) if prop.district_id else None,
        neighborhood=_ref(ctx.neighborhoods.get(prop.neighborhood_id))
        if prop.neighborhood_id
        else None,
        # The street can identify a house: only shown when the exact location is public.
        street=prop.street if (private or prop.location_privacy == "EXACT") else None,
        address_text=prop.address_text,
        location_privacy=prop.location_privacy,
        display_location=_latlon(prop.display_location),
        status=prop.status,
        published_at=prop.published_at,
        expires_at=prop.expires_at,
        verified=prop.verified_at is not None,
        verified_at=prop.verified_at,
        is_demo=prop.is_demo,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
        virtual_tour_url=prop.virtual_tour_url,
        media=[_media_out(m) for m in _visible_media(prop, private)],
        lister=_lister(prop, ctx),
        can_edit=can_edit,
    )
    if private:
        out.exact_location = _latlon(prop.location)
        out.status_reason = prop.status_reason
        out.needs_review = prop.needs_review
        out.show_phone = prop.show_phone
        out.allow_whatsapp = prop.allow_whatsapp
        out.agent_id = prop.agent_id
    return out


def to_cards(db: Session, props: Sequence[Property]) -> list[PropertyCard]:
    ctx = _context(db, props, with_people=False)
    cards = []
    for prop in props:
        agency = ctx.agencies.get(prop.agency_id) if prop.agency_id else None
        cards.append(
            PropertyCard(
                id=prop.id,
                reference_code=prop.reference_code,
                title_ar=prop.title_ar,
                title_en=prop.title_en,
                property_type_code=prop.property_type_code,
                purpose=prop.purpose,
                rent_period=prop.rent_period,
                price_amount=prop.price_amount,
                currency=prop.currency,
                price_on_request=prop.price_on_request,
                area_m2=prop.area_m2,
                bedrooms=prop.bedrooms,
                bathrooms=prop.bathrooms,
                city=_ref(ctx.cities[prop.city_id]),
                district=_ref(ctx.districts.get(prop.district_id)) if prop.district_id else None,
                neighborhood=_ref(ctx.neighborhoods.get(prop.neighborhood_id))
                if prop.neighborhood_id
                else None,
                display_location=_latlon(prop.display_location),
                status=prop.status,
                verified=prop.verified_at is not None,
                is_demo=prop.is_demo,
                published_at=prop.published_at,
                created_at=prop.created_at,
                cover_url=_cover(prop),
                agency_name=agency.name_ar
                if agency and agency.status == AgencyStatus.VERIFIED
                else None,
            )
        )
    return cards
