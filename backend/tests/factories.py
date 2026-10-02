"""Test data builders and API helpers."""

from __future__ import annotations

import io
import re
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.geo.models import City, District, Governorate, Neighborhood
from app.geo.spatial import make_point
from app.notifications.email import MockEmailProvider
from app.rbac.catalog import Role
from app.users.models import User, UserRole, UserStatus

DEFAULT_PASSWORD = "Correct-Horse-Battery-9"


def make_user(
    db: Session,
    *,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
    roles: Iterable[Role] = (Role.CUSTOMER,),
    verified: bool = True,
    name: str = "مستخدم تجريبي",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:10]}@example.com",
        full_name=name,
        password_hash=hash_password(password),
        preferred_locale="ar",
        status=status,
        email_verified_at=datetime.now(UTC) if verified else None,
    )
    for role in {Role.CUSTOMER, *roles}:
        user.role_links.append(UserRole(role_code=role.value))
    db.add(user)
    # Commit (a savepoint release inside the test transaction) so that a failing
    # request, which rolls back its own work, cannot undo test fixtures.
    db.commit()
    return user


def login(api: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    """Bearer-mode login; returns tokens."""
    response = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Auth-Transport": "bearer"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"access": body["access_token"], "refresh": body["refresh_token"]}


def auth_headers(api: TestClient, user: User, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(api, user.email, password)['access']}"}


def token_from_outbox(outbox: MockEmailProvider, tag: str) -> str:
    messages = [m for m in outbox.outbox() if tag in m.tags]
    assert messages, f"no {tag} email sent"
    match = re.search(r"token=([A-Za-z0-9_-]+)", messages[-1].text)
    assert match, "no token link in email"
    return match.group(1)


# --------------------------------------------------------------------------- real-estate helpers

# Real Basra reference points (WGS84).
BASRA_ASHAR = (47.8160, 30.5090)  # (lon, lat) Al-Ashar
BASRA_CORNICHE = (47.8417, 30.5160)


def basra(db: Session) -> tuple[Governorate, City]:
    gov = db.execute(select(Governorate).where(Governorate.code == "BSR")).scalar_one()
    city = db.execute(
        select(City).where(City.governorate_id == gov.id, City.slug == "basra")
    ).scalar_one()
    return gov, city


def make_district(db: Session, city: City, slug: str = "ashar") -> District:
    district = District(
        city_id=city.id, name_ar="العشار", name_en="Al-Ashar", slug=slug, is_active=True
    )
    db.add(district)
    db.commit()
    return district


def make_neighborhood(
    db: Session, district: District, centroid: tuple[float, float] | None = None
) -> Neighborhood:
    hood = Neighborhood(
        district_id=district.id,
        name_ar="الجمهورية",
        name_en="Al-Jumhuriya",
        slug=f"hood-{uuid.uuid4().hex[:6]}",
        centroid=make_point(*centroid) if centroid else None,
        is_active=True,
    )
    db.add(hood)
    db.commit()
    return hood


def listing_payload(gov: Governorate, city: City, **overrides: object) -> dict:
    payload: dict = {
        "title_ar": "بيت للبيع في العشار قرب الكورنيش",
        "description_ar": "بيت مساحته 200 متر مربع، ثلاث غرف نوم، قريب من الخدمات.",
        "property_type_code": "HOUSE",
        "purpose": "SALE",
        "price_amount": "250000000",
        "currency": "IQD",
        "area_m2": "200",
        "bedrooms": 3,
        "bathrooms": 2,
        "governorate_id": str(gov.id),
        "city_id": str(city.id),
        "location": {"lon": BASRA_ASHAR[0], "lat": BASRA_ASHAR[1]},
        "location_privacy": "APPROXIMATE",
        "amenities": ["NATIONAL_GRID", "GENERATOR_SUBSCRIPTION"],
    }
    payload.update(overrides)
    return payload


def image_bytes(fmt: str = "PNG", color: tuple[int, int, int] = (40, 120, 110)) -> bytes:
    img = Image.new("RGB", (640, 480), color)
    for x in range(0, 640, 40):  # some structure so perceptual hashes differ from flat images
        for y in range(480):
            img.putpixel((x, y), (220, 190, 60))
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    return buffer.getvalue()


def upload_image(api: TestClient, headers: dict[str, str], property_id: str) -> dict:
    response = api.post(
        f"/api/v1/properties/{property_id}/media",
        files={"file": ("photo.png", image_bytes(), "image/png")},
        data={"kind": "IMAGE"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def publish(
    api: TestClient,
    owner_headers: dict[str, str],
    moderator_headers: dict[str, str],
    property_id: str,
) -> dict:
    """Upload a photo, submit and approve: returns the approved listing."""
    upload_image(api, owner_headers, property_id)
    submitted = api.post(f"/api/v1/properties/{property_id}/submit", headers=owner_headers)
    assert submitted.status_code == 200, submitted.text
    approved = api.post(
        f"/api/v1/properties/{property_id}/moderate",
        json={"decision": "APPROVE"},
        headers=moderator_headers,
    )
    assert approved.status_code == 200, approved.text
    return approved.json()
