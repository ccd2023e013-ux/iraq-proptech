"""DEMO data for development and demonstrations.

Everything created here is labelled as demo so it can never be mistaken for
real market data:

* listings have ``is_demo=True`` (the UI shows a DEMO banner, search can
  exclude them, pages are ``noindex``), their titles say "تجريبي" and their
  descriptions state that they are not real offers; no photos are invented;
* district polygons are small squares around *approximate* centres and carry
  ``geometry_source = DEMO_GEOMETRY_SOURCE`` — they are placeholders until an
  openly-licensed boundary dataset is imported through the admin API.

Idempotent: running it twice does not duplicate anything. ``reset`` removes
only rows this module created.
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.security import hash_password
from app.geo.models import City, District, Governorate
from app.geo.spatial import coarsen, make_point
from app.properties.models import (
    Property,
    PropertyAmenity,
    PropertyPriceHistory,
    PropertyStatusHistory,
)
from app.properties.service import _next_reference
from app.rbac.catalog import Role
from app.users.models import User, UserRole, UserStatus

DEMO_EMAIL = "demo-listings@example.com"
DEMO_GEOMETRY_SOURCE = "DEMO — approximate square, not an official boundary"
HALF_SIZE = 0.005  # degrees (~1 km squares)


@dataclass(frozen=True)
class DemoDistrict:
    slug: str
    name_ar: str
    name_en: str
    lon: float  # approximate centre
    lat: float


# Basra city areas (names are real; centres approximate; squares are DEMO).
BASRA_DISTRICTS = [
    DemoDistrict("ashar", "العشار", "Al-Ashar", 47.816, 30.512),
    DemoDistrict("baradiyah", "البراضعية", "Al-Baradiyah", 47.790, 30.490),
    DemoDistrict("jazair", "الجزائر", "Al-Jazair", 47.795, 30.515),
    DemoDistrict("jamiyat", "الجمعيات", "Al-Jamiyat", 47.770, 30.520),
    DemoDistrict("tuwaisa", "الطويسة", "Al-Tuwaisa", 47.805, 30.503),
    DemoDistrict("maqal", "المعقل", "Al-Maqal", 47.800, 30.555),
    DemoDistrict("jubaila", "الجبيلة", "Al-Jubaila", 47.825, 30.528),
    DemoDistrict("hay-al-hussein", "حي الحسين", "Hay Al-Hussein", 47.760, 30.505),
]

_TYPES = [
    ("HOUSE", "بيت"),
    ("APARTMENT", "شقة"),
    ("VILLA", "فيلا"),
    ("LAND", "أرض"),
    ("SHOP", "محل"),
]
_AMENITIES = ["PARKING", "PRIVATE_GENERATOR", "SPLIT_AC", "WATER_TANK", "GARDEN", "CCTV"]


def _square(d: DemoDistrict) -> str:
    w, e, s, n = d.lon - HALF_SIZE, d.lon + HALF_SIZE, d.lat - HALF_SIZE, d.lat + HALF_SIZE
    return f"SRID=4326;MULTIPOLYGON((({w} {s},{e} {s},{e} {n},{w} {n},{w} {s})))"


def _demo_user(db: Session) -> User:
    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            full_name="حساب العرض التجريبي (DEMO)",
            # Random unusable password: nobody signs in as the demo lister.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            preferred_locale="ar",
            status=UserStatus.ACTIVE,
            email_verified_at=datetime.now(UTC),
        )
        user.role_links.append(UserRole(role_code=Role.CUSTOMER))
        user.role_links.append(UserRole(role_code=Role.PROPERTY_OWNER))
        db.add(user)
        db.flush()
    return user


def _districts(db: Session, city: City) -> list[tuple[DemoDistrict, District]]:
    out = []
    for d in BASRA_DISTRICTS:
        row = db.execute(
            select(District).where(District.city_id == city.id, District.slug == d.slug)
        ).scalar_one_or_none()
        if row is None:
            row = District(
                city_id=city.id,
                slug=d.slug,
                name_ar=d.name_ar,
                name_en=d.name_en,
                centroid=make_point(d.lon, d.lat),
                boundary=_square(d),
                geometry_source=DEMO_GEOMETRY_SOURCE,
                is_active=True,
            )
            db.add(row)
            db.flush()
        out.append((d, row))
    return out


def seed(db: Session, *, listings: int = 40) -> dict[str, int]:
    """Create the demo lister, demo district squares in Basra and demo listings."""
    gov = db.execute(select(Governorate).where(Governorate.code == "BSR")).scalar_one()
    city = db.execute(
        select(City).where(City.governorate_id == gov.id, City.slug == "basra")
    ).scalar_one()
    user = _demo_user(db)
    districts = _districts(db, city)
    existing = len(
        db.execute(select(Property.id).where(Property.lister_id == user.id)).scalars().all()
    )
    rng = random.Random(2026)  # noqa: S311 - deterministic demo values, not security
    now = datetime.now(UTC)
    created = 0
    for i in range(existing, listings):
        d, district = districts[i % len(districts)]
        code, type_ar = _TYPES[i % len(_TYPES)]
        rent = code in ("APARTMENT", "SHOP") and i % 2 == 0
        usd = not rent and i % 5 == 0
        lon = d.lon + rng.uniform(-HALF_SIZE * 0.8, HALF_SIZE * 0.8)
        lat = d.lat + rng.uniform(-HALF_SIZE * 0.8, HALF_SIZE * 0.8)
        privacy = "EXACT" if i % 4 == 0 else "APPROXIMATE"
        display = (lon, lat) if privacy == "EXACT" else coarsen(lon, lat)
        land = code == "LAND"
        area = Decimal(rng.choice([100, 150, 200, 250, 300, 400, 600]))
        if rent:
            price = Decimal(rng.randrange(400, 2500) * 1000)
        elif usd:
            price = Decimal(rng.randrange(60, 600) * 1000)
        else:
            price = Decimal(rng.randrange(60, 900) * 1_000_000)
        prop = Property(
            reference_code=_next_reference(db, gov),
            title_ar=f"عقار تجريبي — {type_ar} في {d.name_ar}",
            title_en=f"DEMO listing — {code.replace('_', ' ').title()} in {d.name_en}",
            description_ar=(
                "هذا إعلان تجريبي لأغراض العرض فقط وليس عرضاً حقيقياً. "
                "المواصفات والسعر أرقام توضيحية."
            ),
            description_en="Demo listing for demonstration only — not a real offer.",
            property_type_code=code,
            purpose="RENT" if rent else "SALE",
            rent_period="MONTHLY" if rent else None,
            price_amount=price,
            currency="USD" if usd else "IQD",
            price_on_request=False,
            negotiable=i % 3 == 0,
            area_m2=area,
            bedrooms=None if land or code == "SHOP" else rng.randint(1, 6),
            bathrooms=None if land or code == "SHOP" else rng.randint(1, 4),
            governorate_id=gov.id,
            city_id=city.id,
            district_id=district.id,
            location=make_point(lon, lat),
            display_location=make_point(*display),
            location_privacy=privacy,
            status="APPROVED",
            published_at=now - timedelta(hours=i * 7),
            expires_at=now + timedelta(days=90),
            lister_id=user.id,
            ownership_document="UNKNOWN",
            needs_review=False,
            show_phone=False,
            allow_whatsapp=False,
            is_demo=True,
        )
        if not land:
            prop.amenity_links = [
                PropertyAmenity(amenity_code=c) for c in rng.sample(_AMENITIES, k=rng.randint(1, 4))
            ]
        db.add(prop)
        db.flush()
        db.add(
            PropertyStatusHistory(
                property_id=prop.id,
                from_status=None,
                to_status="APPROVED",
                changed_by_id=None,
                reason="demo seed",
            )
        )
        db.add(
            PropertyPriceHistory(
                property_id=prop.id,
                price_amount=prop.price_amount,
                currency=prop.currency,
                price_on_request=False,
                changed_by_id=None,
            )
        )
        created += 1
    audit.record(
        db,
        "demo.seeded",
        actor_id=None,
        resource_type="demo",
        data={"listings_created": created, "districts": len(districts)},
    )
    db.commit()
    return {"listings_created": created, "districts": len(districts)}


def reset(db: Session) -> dict[str, int]:
    """Delete demo listings (and their history). Demo districts are kept if referenced."""
    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
    if user is None:
        return {"listings_deleted": 0}
    ids = list(
        db.execute(
            select(Property.id).where(Property.lister_id == user.id, Property.is_demo.is_(True))
        ).scalars()
    )
    for model in (PropertyStatusHistory, PropertyPriceHistory, PropertyAmenity):
        db.execute(delete(model).where(model.property_id.in_(ids)))
    db.execute(delete(Property).where(Property.id.in_(ids)))
    audit.record(db, "demo.reset", actor_id=None, resource_type="demo", data={"deleted": len(ids)})
    db.commit()
    return {"listings_deleted": len(ids)}
