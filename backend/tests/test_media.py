"""Media and private documents: validation, privacy, authorization, audit."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.config import get_settings
from app.rbac.catalog import Role
from tests.factories import (
    auth_headers,
    basra,
    image_bytes,
    listing_payload,
    make_user,
    publish,
    upload_image,
)

pytestmark = pytest.mark.db


@pytest.fixture
def setup(api: TestClient, db_session: Session) -> dict:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    headers = auth_headers(api, owner)
    listing = api.post(
        "/api/v1/properties", json=listing_payload(*basra(db_session)), headers=headers
    ).json()
    mod = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    return {"headers": headers, "id": listing["id"], "mod": mod}


def test_image_is_reencoded_and_metadata_stripped(api: TestClient, setup: dict) -> None:
    img = Image.new("RGB", (1200, 900), (10, 90, 80))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # camera make
    exif[0x0132] = "2026:01:01 10:00:00"  # timestamp
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", exif=exif.tobytes())
    response = api.post(
        f"/api/v1/properties/{setup['id']}/media",
        files={"file": ("home.jpg", buffer.getvalue(), "image/jpeg")},
        data={"kind": "IMAGE", "caption": "الواجهة"},
        headers=setup["headers"],
    )
    assert response.status_code == 201, response.text
    media = response.json()
    assert media["content_type"] == "image/webp"
    stored = api.get(media["url"], headers=setup["headers"])
    assert stored.status_code == 200
    out = Image.open(io.BytesIO(stored.content))
    assert out.format == "WEBP"
    assert not out.getexif()  # no camera data / timestamps / GPS survive re-encoding


def test_rejects_non_images_regardless_of_declared_type(api: TestClient, setup: dict) -> None:
    response = api.post(
        f"/api/v1/properties/{setup['id']}/media",
        files={"file": ("x.jpg", b"<script>alert(1)</script>", "image/jpeg")},
        headers=setup["headers"],
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE"


def test_rejects_oversized_images(api: TestClient, setup: dict) -> None:
    settings = get_settings()
    previous = settings.max_image_bytes
    settings.max_image_bytes = 1000
    try:
        response = api.post(
            f"/api/v1/properties/{setup['id']}/media",
            files={"file": ("big.png", image_bytes(), "image/png")},
            headers=setup["headers"],
        )
    finally:
        settings.max_image_bytes = previous
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_media_visibility_follows_listing(
    api: TestClient, setup: dict, db_session: Session
) -> None:
    media = upload_image(api, setup["headers"], setup["id"])
    assert api.get(media["url"]).status_code == 404  # draft: not public
    private = api.get(media["url"], headers=setup["headers"])
    assert private.headers["cache-control"] == "private, no-store"

    api.post(f"/api/v1/properties/{setup['id']}/submit", headers=setup["headers"])
    api.post(
        f"/api/v1/properties/{setup['id']}/moderate",
        json={"decision": "APPROVE"},
        headers=setup["mod"],
    )
    public = api.get(media["thumbnail_url"])
    assert public.status_code == 200
    assert public.headers["cache-control"].startswith("public")
    assert public.headers["x-content-type-options"] == "nosniff"
    etag = public.headers["etag"]
    assert api.get(media["thumbnail_url"], headers={"If-None-Match": etag}).status_code == 304

    # A moderator can hide a single image without touching the listing.
    hidden = api.post(f"/api/v1/media/{media['id']}/moderate?state=REJECTED", headers=setup["mod"])
    assert hidden.status_code == 200
    assert api.get(media["url"]).status_code == 404


def test_reorder_and_delete_media(api: TestClient, setup: dict) -> None:
    first = upload_image(api, setup["headers"], setup["id"])
    second = upload_image(api, setup["headers"], setup["id"])
    bad = api.put(
        f"/api/v1/properties/{setup['id']}/media/order",
        json={"media_ids": [first["id"]]},
        headers=setup["headers"],
    )
    assert bad.json()["error"]["code"] == "INVALID_ORDER"
    ok = api.put(
        f"/api/v1/properties/{setup['id']}/media/order",
        json={"media_ids": [second["id"], first["id"]]},
        headers=setup["headers"],
    )
    assert ok.status_code == 204
    detail = api.get(f"/api/v1/properties/{setup['id']}", headers=setup["headers"]).json()
    assert [m["id"] for m in detail["media"]] == [second["id"], first["id"]]
    deleted = api.delete(
        f"/api/v1/properties/{setup['id']}/media/{first['id']}", headers=setup["headers"]
    )
    assert deleted.status_code == 204
    assert api.get(first["url"], headers=setup["headers"]).status_code == 404


def test_other_users_cannot_upload(api: TestClient, setup: dict, db_session: Session) -> None:
    publish(api, setup["headers"], setup["mod"], setup["id"])
    other = auth_headers(api, make_user(db_session, roles=[Role.PROPERTY_OWNER]))
    response = api.post(
        f"/api/v1/properties/{setup['id']}/media",
        files={"file": ("p.png", image_bytes(), "image/png")},
        headers=other,
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- private documents


def _upload_pdf(api: TestClient, setup: dict) -> dict:
    response = api.post(
        f"/api/v1/properties/{setup['id']}/documents",
        files={"file": ("../../صك الطابو.pdf", b"%PDF-1.7\n%demo\n", "application/pdf")},
        data={"doc_type": "TITLE_DEED"},
        headers=setup["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_documents_are_private_and_downloads_audited(
    api: TestClient, setup: dict, db_session: Session
) -> None:
    publish(api, setup["headers"], setup["mod"], setup["id"])
    document = _upload_pdf(api, setup)
    assert document["filename"] == "صك الطابو.pdf"  # path parts stripped

    # Anonymous and unrelated users cannot list or download, even when the listing is public.
    stranger = auth_headers(api, make_user(db_session))
    assert (
        api.get(f"/api/v1/properties/{setup['id']}/documents", headers=stranger).status_code == 404
    )
    assert api.get(f"/api/v1/documents/{document['id']}", headers=stranger).status_code == 404
    assert api.get(f"/api/v1/documents/{document['id']}").status_code == 401

    download = api.get(f"/api/v1/documents/{document['id']}", headers=setup["mod"])
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")
    assert download.headers["cache-control"] == "private, no-store"
    assert "attachment" in download.headers["content-disposition"]
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.action == "property.document_downloaded")
    ).scalars()
    assert len(list(audit)) == 1


def test_documents_reject_unknown_formats(api: TestClient, setup: dict) -> None:
    response = api.post(
        f"/api/v1/properties/{setup['id']}/documents",
        files={"file": ("deed.docx", b"PK\x03\x04 not allowed", "application/pdf")},
        headers=setup["headers"],
    )
    assert response.status_code == 415
