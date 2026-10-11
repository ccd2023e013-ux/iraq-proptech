"""National Iraqi DEMO dataset for the public demonstration site.

Seven cities (Basra, Baghdad, Najaf, Karbala, Erbil, Mosul, Sulaymaniyah),
18 synthetic listings each, with representative DEMO photos, demo areas and
demo points of interest, plus optional demo accounts (admin, agency owner,
agent, private owner, customer) whose shared password comes from the
environment — never from source code.

The demo ADMIN never uses the shared password in production: there it exists
only with its own ``DEMO_ADMIN_PASSWORD`` (policy-checked, different from the
shared one). Without it, a production run creates no demo admin and disables an
existing one (ADMIN role removed, password made unusable, account deactivated,
sessions revoked). Outside production the previous behaviour is kept.

Honesty rules (same as ``app.demo``):

* every listing has ``is_demo=True``, says "إعلان تجريبي" / "DEMO" in its title
  and states in its description that it is not a real offer;
* area squares are placeholders (``DEMO_GEOMETRY_SOURCE``); a few well-known
  district names are used with *approximate* centres, the other areas are
  explicitly synthetic ("المنطقة الشمالية (تجريبية)");
* images are representative licensed photos (app/demo_photos) captioned as such,
  or labelled illustrations where no photo of the type exists.

Idempotent: listings are counted per city and only the missing ones are
created; accounts are created once and their password is (re)set from the
environment on each run.
"""

from __future__ import annotations

import logging
import random
import secrets
import uuid
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agencies.models import Agency, AgencyMember, AgencyStatus, AgentProfile, MemberRole
from app.audit import service as audit
from app.auth.security import hash_password
from app.auth.service import revoke_all_sessions
from app.demo import BASRA_DISTRICTS, DEMO_GEOMETRY_SOURCE, HALF_SIZE, DemoDistrict
from app.demo import _districts as basra_districts
from app.demo_images import attach_demo_image
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
from app.users.validation import password_problems

logger = logging.getLogger(__name__)

LISTER_EMAIL = "demo-iraq-listings@example.com"
LISTINGS_PER_CITY = 18
AGENCY_SLUG = "demo-rafidain-real-estate"

# Demo accounts (emails are reserved example.com addresses; no real people).
DEMO_ADMIN_EMAIL = "demo.admin@example.com"
DEMO_ACCOUNTS: list[tuple[str, str, Role | None]] = [
    (DEMO_ADMIN_EMAIL, "مدير تجريبي (DEMO)", Role.ADMIN),
    ("demo.agency@example.com", "صاحب مكتب تجريبي (DEMO)", Role.AGENCY_OWNER),
    ("demo.agent@example.com", "وكيل عقاري تجريبي (DEMO)", Role.AGENT),
    ("demo.owner@example.com", "مالك عقار تجريبي (DEMO)", Role.PROPERTY_OWNER),
    ("demo.customer@example.com", "زبون تجريبي (DEMO)", None),
]


@dataclass(frozen=True)
class CitySpec:
    gov_code: str
    city_slug: str
    name_ar: str
    name_en: str
    currency: str  # main currency used in this market for sales
    sale_house_m: tuple[int, int]  # IQD millions or USD thousands
    sale_apartment_m: tuple[int, int]
    rent_k: tuple[int, int]  # monthly rent: IQD thousands or USD
    districts: tuple[DemoDistrict, ...]


def _area(slug: str, name_ar: str, name_en: str, lon: float, lat: float) -> DemoDistrict:
    return DemoDistrict(slug, name_ar, name_en, lon, lat)


def _synthetic(slug: str, side_ar: str, side_en: str, lon: float, lat: float) -> DemoDistrict:
    return DemoDistrict(
        f"demo-{slug}", f"المنطقة {side_ar} (تجريبية)", f"{side_en} area (demo)", lon, lat
    )


CITIES: tuple[CitySpec, ...] = (
    CitySpec(
        "BSR",
        "basra",
        "البصرة",
        "Basra",
        "IQD",
        (150, 900),
        (80, 300),
        (400, 1800),
        tuple(BASRA_DISTRICTS),
    ),
    CitySpec(
        "BGD",
        "baghdad",
        "بغداد",
        "Baghdad",
        "IQD",
        (250, 1500),
        (100, 450),
        (500, 2500),
        (
            _area("mansour", "المنصور", "Al-Mansour", 44.345, 33.318),
            _area("karrada", "الكرادة", "Al-Karrada", 44.425, 33.302),
            _area("adhamiya", "الأعظمية", "Al-Adhamiya", 44.372, 33.371),
            _area("jadriya", "الجادرية", "Al-Jadriya", 44.383, 33.278),
            _area("zayouna", "زيونة", "Zayouna", 44.462, 33.326),
            _area("yarmouk", "اليرموك", "Al-Yarmouk", 44.338, 33.297),
        ),
    ),
    CitySpec(
        "NJF",
        "najaf",
        "النجف",
        "Najaf",
        "IQD",
        (150, 800),
        (80, 250),
        (350, 1500),
        (
            _area("old-city", "المدينة القديمة", "Old City", 44.316, 31.998),
            _synthetic("north", "الشمالية", "North", 44.335, 32.030),
            _synthetic("east", "الشرقية", "East", 44.362, 32.014),
            _synthetic("northeast", "الشمالية الشرقية", "North-east", 44.358, 32.040),
        ),
    ),
    CitySpec(
        "KRB",
        "karbala",
        "كربلاء",
        "Karbala",
        "IQD",
        (150, 750),
        (80, 250),
        (350, 1400),
        (
            _area("old-city", "المدينة القديمة", "Old City", 44.032, 32.616),
            _synthetic("north", "الشمالية", "North", 44.025, 32.640),
            _synthetic("east", "الشرقية", "East", 44.052, 32.615),
            _synthetic("south", "الجنوبية", "South", 44.020, 32.595),
        ),
    ),
    CitySpec(
        "EBL",
        "erbil",
        "أربيل",
        "Erbil",
        "USD",
        (90, 650),
        (50, 220),
        (400, 1600),
        (
            _area("centre", "مركز المدينة", "City centre", 44.009, 36.191),
            _area("ankawa", "عنكاوا", "Ankawa", 43.993, 36.228),
            _synthetic("east", "الشرقية", "East", 44.045, 36.195),
            _synthetic("south", "الجنوبية", "South", 44.010, 36.160),
        ),
    ),
    CitySpec(
        "NIN",
        "mosul",
        "الموصل",
        "Mosul",
        "IQD",
        (90, 500),
        (60, 200),
        (250, 1000),
        (
            _area("old-city", "الموصل القديمة", "Old City", 43.128, 36.340),
            _synthetic("left-bank", "الساحل الأيسر", "Left bank", 43.160, 36.355),
            _synthetic("north", "الشمالية", "North", 43.130, 36.372),
            _synthetic("west", "الغربية", "West", 43.095, 36.330),
        ),
    ),
    CitySpec(
        "SUL",
        "sulaymaniyah",
        "السليمانية",
        "Sulaymaniyah",
        "USD",
        (80, 550),
        (45, 200),
        (350, 1400),
        (
            _area("centre", "مركز المدينة", "City centre", 45.433, 35.561),
            _synthetic("north", "الشمالية", "North", 45.430, 35.585),
            _synthetic("west", "الغربية", "West", 45.400, 35.560),
            _synthetic("east", "الشرقية", "East", 45.460, 35.555),
        ),
    ),
)

# (type, purpose) mix per city: every city has houses for sale and apartments
# for rent, so the canonical example searches always find something.
_MIX: tuple[tuple[str, str], ...] = (
    ("HOUSE", "SALE"),
    ("APARTMENT", "RENT"),
    ("APARTMENT", "SALE"),
    ("HOUSE", "RENT"),
    ("VILLA", "SALE"),
    ("LAND", "SALE"),
    ("SHOP", "RENT"),
    ("HOUSE", "SALE"),
    ("APARTMENT", "RENT"),
    ("OFFICE", "RENT"),
    ("HOUSE", "SALE"),
    ("APARTMENT", "SALE"),
    ("LAND", "SALE"),
    ("VILLA", "RENT"),
    ("HOUSE", "RENT"),
    ("APARTMENT", "RENT"),
    ("SHOP", "SALE"),
    ("HOUSE", "SALE"),
)

_TYPE_NAMES = {
    "HOUSE": ("بيت", "House"),
    "APARTMENT": ("شقة", "Apartment"),
    "VILLA": ("فيلا", "Villa"),
    "LAND": ("قطعة أرض", "Land plot"),
    "SHOP": ("محل تجاري", "Shop"),
    "OFFICE": ("مكتب", "Office"),
}
_PURPOSE_NAMES = {"SALE": ("للبيع", "for sale"), "RENT": ("للإيجار", "for rent")}
_RESIDENTIAL_AMENITIES = [
    "NATIONAL_GRID",
    "GENERATOR_SUBSCRIPTION",
    "WATER_TANK",
    "SPLIT_AC",
    "KITCHEN_EQUIPPED",
    "GUEST_ROOM",
    "PARKING",
    "GARDEN",
    "ROOF_ACCESS",
    "SOLAR_PANELS",
    "INTERNET_FIBER",
]
_COMMERCIAL_AMENITIES = ["NATIONAL_GRID", "PRIVATE_GENERATOR", "PARKING", "CCTV", "INTERNET_FIBER"]
_POIS = [
    ("SCHOOL", "مدرسة تجريبية", "Demo school", 0.002, 0.001),
    ("HOSPITAL", "مستشفى تجريبي", "Demo hospital", -0.003, 0.002),
    ("MOSQUE", "جامع تجريبي", "Demo mosque", 0.001, -0.002),
    ("MARKET", "سوق تجريبي", "Demo market", -0.001, -0.003),
]


# --------------------------------------------------------------------------- accounts


def _user(db: Session, email: str, name: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            full_name=name,
            password_hash=hash_password(secrets.token_urlsafe(32)),  # unusable until set
            preferred_locale="ar",
            status=UserStatus.ACTIVE,
            email_verified_at=datetime.now(UTC),
        )
        user.role_links.append(UserRole(role_code=Role.CUSTOMER))
        db.add(user)
        db.flush()
    return user


def _ensure_role(user: User, role: Role) -> None:
    if role not in user.roles:
        user.role_links.append(UserRole(role_code=role.value))


def _disable_demo_admin(db: Session) -> None:
    """Production without ``DEMO_ADMIN_PASSWORD``: no usable demo admin may remain.

    Removes the ADMIN role, replaces the password with an unusable random one,
    deactivates the account and revokes its sessions (access tokens are refused
    on the next request because the account is no longer ACTIVE). Idempotent.
    """
    user = db.execute(select(User).where(User.email == DEMO_ADMIN_EMAIL)).scalar_one_or_none()
    if user is None:
        return
    admin_links = [link for link in user.role_links if Role(link.role_code) == Role.ADMIN]
    if not admin_links and user.status != UserStatus.ACTIVE:
        return  # already disabled
    for link in admin_links:
        user.role_links.remove(link)
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    if user.status == UserStatus.ACTIVE:
        user.status = UserStatus.DEACTIVATED
    revoke_all_sessions(db, user.id, reason="demo_admin_disabled", actor_id=None)
    audit.record(
        db,
        "demo.admin_disabled",
        actor_id=None,
        resource_type="user",
        resource_id=user.id,
        data={"reason": "production without DEMO_ADMIN_PASSWORD"},
    )
    db.flush()
    logger.warning(
        "Demo admin disabled: production requires its own DEMO_ADMIN_PASSWORD "
        "(the shared demo password is never used for an admin)"
    )


def ensure_accounts(
    db: Session,
    password: str | None,
    *,
    admin_password: str | None = None,
    production: bool = False,
) -> dict[str, uuid.UUID]:
    """Demo agency + accounts. Passwords are set only when ``password`` is given.

    The demo ADMIN: outside production it uses ``admin_password`` when given,
    otherwise the shared ``password`` (unchanged behaviour). In production it
    exists only with its own ``admin_password``; without one it is not created
    and an existing one is disabled (``_disable_demo_admin``).
    """
    if password:
        problems = password_problems(password)
        if problems:
            raise ValueError(f"DEMO_ACCOUNT_PASSWORD rejected: {', '.join(problems)}")
    if admin_password:
        problems = password_problems(admin_password)
        if problems:
            raise ValueError(f"DEMO_ADMIN_PASSWORD rejected: {', '.join(problems)}")
        if password and admin_password == password:
            raise ValueError("DEMO_ADMIN_PASSWORD must differ from DEMO_ACCOUNT_PASSWORD")
    ids: dict[str, uuid.UUID] = {}
    for email, name, role in DEMO_ACCOUNTS:
        if role is Role.ADMIN:
            if production and not admin_password:
                _disable_demo_admin(db)
                continue
            admin = _user(db, email, name)
            _ensure_role(admin, role)
            secret = admin_password or password
            if secret:
                admin.password_hash = hash_password(secret)
            if production and admin.status == UserStatus.DEACTIVATED:
                # Disabled earlier for lack of a dedicated password; the owner has
                # now configured one. A SUSPENDED account is left to the admins.
                admin.status = UserStatus.ACTIVE
            ids[email] = admin.id
            continue
        user = _user(db, email, name)
        if role is not None:
            _ensure_role(user, role)
        if password:
            user.password_hash = hash_password(password)
        ids[email] = user.id
    db.flush()

    basra = db.execute(select(City).where(City.slug == "basra")).scalar_one()
    agency = db.execute(select(Agency).where(Agency.slug == AGENCY_SLUG)).scalar_one_or_none()
    if agency is None:
        agency = Agency(
            name_ar="مكتب الرافدين العقاري (تجريبي)",
            name_en="Al-Rafidain Real Estate (demo)",
            slug=AGENCY_SLUG,
            description="مكتب تجريبي لأغراض العرض فقط — ليس مكتباً حقيقياً.",
            city_id=basra.id,
            status=AgencyStatus.VERIFIED,
            verified_at=datetime.now(UTC),
            created_by_id=ids["demo.agency@example.com"],
            is_demo=True,
        )
        db.add(agency)
        db.flush()
    for email, member_role in (
        ("demo.agency@example.com", MemberRole.OWNER),
        ("demo.agent@example.com", MemberRole.AGENT),
    ):
        uid = ids[email]
        if db.execute(select(AgencyMember).where(AgencyMember.user_id == uid)).first() is None:
            db.add(AgencyMember(agency_id=agency.id, user_id=uid, role=member_role))
    agent_id = ids["demo.agent@example.com"]
    if db.get(AgentProfile, agent_id) is None:
        db.add(
            AgentProfile(
                user_id=agent_id,
                display_name="وكيل عقاري تجريبي (DEMO)",
                bio="حساب وكيل تجريبي لأغراض العرض فقط.",
                years_experience=5,
                languages="ar,en",
            )
        )
    db.flush()
    ids["agency"] = agency.id
    return ids


# --------------------------------------------------------------------------- places


def _city(db: Session, spec: CitySpec) -> tuple[Governorate, City]:
    gov = db.execute(select(Governorate).where(Governorate.code == spec.gov_code)).scalar_one()
    city = db.execute(
        select(City).where(City.governorate_id == gov.id, City.slug == spec.city_slug)
    ).scalar_one()
    return gov, city


def _square(d: DemoDistrict) -> str:
    w, e, s, n = d.lon - HALF_SIZE, d.lon + HALF_SIZE, d.lat - HALF_SIZE, d.lat + HALF_SIZE
    return f"SRID=4326;MULTIPOLYGON((({w} {s},{e} {s},{e} {n},{w} {n},{w} {s})))"


def _areas(db: Session, spec: CitySpec, city: City) -> list[tuple[DemoDistrict, District]]:
    if spec.city_slug == "basra":
        return basra_districts(db, city)
    out = []
    for d in spec.districts:
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


def _pois(db: Session, spec: CitySpec, areas: list[tuple[DemoDistrict, District]]) -> int:
    from app.geo.pois import PointOfInterest

    created = 0
    for d, district in areas:
        for category, name_ar, name_en, dx, dy in _POIS:
            ref = f"demo-iraq:{spec.city_slug}:{d.slug}:{category.lower()}"
            if db.execute(
                select(PointOfInterest.id).where(PointOfInterest.external_ref == ref)
            ).first():
                continue
            db.add(
                PointOfInterest(
                    category=category,
                    name_ar=f"{name_ar} — {d.name_ar}",
                    name_en=f"{name_en} — {d.name_en}",
                    location=make_point(d.lon + dx, d.lat + dy),
                    city_id=district.city_id,
                    source="DEMO — not a real place",
                    external_ref=ref,
                    is_demo=True,
                    is_active=True,
                )
            )
            created += 1
    return created


# --------------------------------------------------------------------------- listings


def _price(rng: random.Random, spec: CitySpec, code: str, purpose: str) -> tuple[Decimal, str]:
    usd = spec.currency == "USD"
    if purpose == "RENT":
        lo, hi = spec.rent_k
        if code in ("SHOP", "OFFICE", "VILLA"):
            lo, hi = lo * 2, hi * 2
        amount = rng.randrange(lo, hi) // 10 * 10
        return (Decimal(amount) if usd else Decimal(amount * 1000)), spec.currency
    lo, hi = spec.sale_apartment_m if code == "APARTMENT" else spec.sale_house_m
    if code == "VILLA":
        lo, hi = hi // 2, hi * 2
    if code in ("LAND", "SHOP"):
        lo, hi = max(lo // 2, 20), hi
    amount = rng.randrange(lo, hi)
    return (Decimal(amount * 1000) if usd else Decimal(amount * 1_000_000)), spec.currency


def _description(
    spec: CitySpec, d: DemoDistrict, code: str, purpose: str, bedrooms: int | None, area: int
) -> tuple[str, str]:
    type_ar, type_en = _TYPE_NAMES[code]
    purpose_ar, purpose_en = _PURPOSE_NAMES[purpose]
    rooms_ar = f" يتكون من {bedrooms} غرف نوم،" if bedrooms else ""
    rooms_en = f" {bedrooms} bedrooms," if bedrooms else ""
    ar = (
        f"{type_ar} {purpose_ar} في {d.name_ar} بمدينة {spec.name_ar}، بمساحة {area} م².{rooms_ar}"
        " قريب من الخدمات والطرق الرئيسية.\n\n"
        "تنبيه: هذا إعلان تجريبي (DEMO) لعرض إمكانات المنصة فقط وليس عرضاً حقيقياً. "
        "الصور تمثيلية (من Wikimedia Commons) وليست صوراً لهذا العقار، "
        "والسعر والمواصفات أرقام افتراضية."
    )
    en = (
        f"{type_en} {purpose_en} in {d.name_en}, {spec.name_en}: {area} m²,{rooms_en}"
        " close to services and main roads.\n\n"
        "Note: DEMO listing for demonstrating the platform only — not a real offer. "
        "Photos are representative (Wikimedia Commons), not of this property; price and details "
        "are hypothetical."
    )
    return ar, en


def _attach_image(db: Session, prop: Property, seed: int) -> None:
    attach_demo_image(db, prop, seed)


def _city_listings(
    db: Session,
    spec: CitySpec,
    gov: Governorate,
    city: City,
    areas: list[tuple[DemoDistrict, District]],
    *,
    lister: User,
    agency_id: uuid.UUID | None,
    agent_id: uuid.UUID | None,
    target: int,
    images: bool,
) -> int:
    owners = [lister.id] + ([agent_id] if agent_id else [])
    existing = db.execute(
        select(func.count())
        .select_from(Property)
        .where(Property.city_id == city.id, Property.lister_id.in_(owners), Property.is_demo)
    ).scalar_one()
    now = datetime.now(UTC)
    created = 0
    for i in range(existing, target):
        # One generator per listing: re-runs produce the same values for index i.
        rng = random.Random(f"iraq-demo:{spec.city_slug}:{i}")  # noqa: S311 - demo values
        code, purpose = _MIX[i % len(_MIX)]
        d, district = areas[i % len(areas)]
        type_ar, type_en = _TYPE_NAMES[code]
        purpose_ar, purpose_en = _PURPOSE_NAMES[purpose]
        lon = d.lon + rng.uniform(-HALF_SIZE * 0.8, HALF_SIZE * 0.8)
        lat = d.lat + rng.uniform(-HALF_SIZE * 0.8, HALF_SIZE * 0.8)
        privacy = "EXACT" if i % 3 == 0 else "APPROXIMATE"
        display = (lon, lat) if privacy == "EXACT" else coarsen(lon, lat)
        residential = code in ("HOUSE", "APARTMENT", "VILLA")
        area = {
            "HOUSE": rng.choice([150, 200, 250, 300, 400]),
            "APARTMENT": rng.choice([90, 110, 130, 150, 180]),
            "VILLA": rng.choice([400, 500, 600, 800]),
            "LAND": rng.choice([200, 250, 300, 400, 600, 1000]),
            "SHOP": rng.choice([30, 40, 60, 80]),
            "OFFICE": rng.choice([60, 80, 120, 150]),
        }[code]
        bedrooms = (
            {
                "HOUSE": rng.randint(3, 6),
                "APARTMENT": rng.randint(1, 4),
                "VILLA": rng.randint(4, 7),
            }[code]
            if residential
            else None
        )
        bathrooms = max(1, (bedrooms or 0) // 2 + rng.randint(0, 1)) if residential else None
        price, currency = _price(rng, spec, code, purpose)
        by_agency = agency_id is not None and i % 3 == 1
        desc_ar, desc_en = _description(spec, d, code, purpose, bedrooms, area)
        prop = Property(
            reference_code=_next_reference(db, gov),
            title_ar=f"{type_ar} {purpose_ar} في {d.name_ar}، {spec.name_ar} — إعلان تجريبي",
            title_en=f"DEMO: {type_en} {purpose_en} in {d.name_en}, {spec.name_en}",
            description_ar=desc_ar,
            description_en=desc_en,
            property_type_code=code,
            purpose=purpose,
            rent_period="MONTHLY" if purpose == "RENT" else None,
            price_amount=price,
            currency=currency,
            price_on_request=False,
            negotiable=i % 4 == 0,
            area_m2=Decimal(area),
            land_area_m2=Decimal(area) if code in ("HOUSE", "VILLA", "LAND") else None,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            floors=rng.randint(1, 2) if code in ("HOUSE", "VILLA") else None,
            floor_number=rng.randint(1, 9) if code == "APARTMENT" else None,
            year_built=rng.randint(1995, 2024) if code != "LAND" else None,
            condition=rng.choice(["NEW", "GOOD", "NEEDS_RENOVATION"]) if code != "LAND" else None,
            furnishing=rng.choice(["UNFURNISHED", "SEMI_FURNISHED", "FURNISHED"])
            if residential
            else None,
            governorate_id=gov.id,
            city_id=city.id,
            district_id=district.id,
            location=make_point(lon, lat),
            display_location=make_point(*display),
            location_privacy=privacy,
            status="APPROVED",
            published_at=now - timedelta(hours=i * 5 + rng.randint(0, 4)),
            expires_at=now + timedelta(days=120),
            lister_id=agent_id if by_agency and agent_id else lister.id,
            agency_id=agency_id if by_agency else None,
            agent_id=agent_id if by_agency else None,
            ownership_document="UNKNOWN",
            needs_review=False,
            show_phone=False,
            allow_whatsapp=False,
            is_demo=True,
            featured_until=now + timedelta(days=30) if i in (0, 4) else None,
        )
        if code != "LAND":
            pool = _RESIDENTIAL_AMENITIES if residential else _COMMERCIAL_AMENITIES
            prop.amenity_links = [
                PropertyAmenity(amenity_code=c) for c in rng.sample(pool, k=rng.randint(2, 5))
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
        if images:
            _attach_image(db, prop, seed=zlib.crc32(f"{spec.city_slug}:{i}".encode()) % 10_000)
        created += 1
    return created


def seed(
    db: Session,
    *,
    per_city: int = LISTINGS_PER_CITY,
    account_password: str | None = None,
    admin_password: str | None = None,
    production: bool = False,
    images: bool = True,
) -> dict[str, int]:
    accounts = ensure_accounts(
        db, account_password, admin_password=admin_password, production=production
    )
    lister = _user(db, LISTER_EMAIL, "حساب العرض التجريبي — العراق (DEMO)")
    _ensure_role(lister, Role.PROPERTY_OWNER)
    db.flush()
    totals = {"listings_created": 0, "areas": 0, "pois_created": 0, "cities": 0}
    for spec in CITIES:
        gov, city = _city(db, spec)
        areas = _areas(db, spec, city)
        totals["areas"] += len(areas)
        totals["pois_created"] += _pois(db, spec, areas) if spec.city_slug != "basra" else 0
        totals["listings_created"] += _city_listings(
            db,
            spec,
            gov,
            city,
            areas,
            lister=lister,
            agency_id=accounts["agency"],
            agent_id=accounts["demo.agent@example.com"],
            target=per_city,
            images=images,
        )
        totals["cities"] += 1
        db.commit()  # one city at a time keeps transactions short on a free database
    audit.record(db, "demo.iraq_seeded", actor_id=None, resource_type="demo", data=totals)
    db.commit()
    return totals
