"""Property Media Studio: storyboards from listing facts, validated video outputs."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.rbac.catalog import Role
from app.studio.service import sniff_video
from tests.factories import auth_headers, make_listing, make_user

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 4096
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4096


def test_sniff_video() -> None:
    assert sniff_video(WEBM) == "video/webm"
    assert sniff_video(MP4) == "video/mp4"
    assert sniff_video(b"<html>" + b"\x00" * 100) is None


@pytest.mark.db
def test_storyboard_and_output_lifecycle(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    other = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    customer = make_user(db_session, roles=[Role.CUSTOMER])
    listing = make_listing(db_session, owner, area_m2=Decimal("180"), bedrooms=4)
    headers = auth_headers(api, owner)

    # Only people who can list properties, and only for listings they manage.
    assert (
        api.post(
            "/api/v1/studio/jobs",
            headers=auth_headers(api, customer),
            json={"property_id": str(listing.id)},
        ).status_code
        == 403
    )
    denied = api.post(
        "/api/v1/studio/jobs",
        headers=auth_headers(api, other),
        json={"property_id": str(listing.id)},
    )
    assert denied.status_code == 403

    created = api.post(
        "/api/v1/studio/jobs",
        headers=headers,
        json={"property_id": str(listing.id), "format": "vertical"},
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["renderer"] == "BROWSER" and job["status"] == "STORYBOARD_READY"
    sb = job["storyboard"]
    assert sb["size"] == [1080, 1920]
    assert sb["property"]["area_m2"] == "180" and sb["property"]["bedrooms"] == 4
    assert sb["scenes"][0]["type"] == "map_intro"
    assert sb["scenes"][-1]["type"] == "cta"

    url = f"/api/v1/studio/jobs/{job['id']}/output"
    bad_type = api.put(url, headers={**headers, "Content-Type": "text/html"}, content=WEBM)
    assert bad_type.status_code == 415
    mismatch = api.put(url, headers={**headers, "Content-Type": "video/mp4"}, content=WEBM)
    assert mismatch.status_code == 422
    tiny = api.put(
        url, headers={**headers, "Content-Type": "video/webm"}, content=b"\x1a\x45\xdf\xa3"
    )
    assert tiny.status_code == 413

    ok = api.put(
        url,
        headers={**headers, "Content-Type": "video/webm;codecs=vp9", "X-Duration-Ms": "18000"},
        content=WEBM,
    )
    assert ok.status_code == 200, ok.text
    done = ok.json()
    assert done["status"] == "DONE" and done["duration_ms"] == 18000
    video = api.get(done["video_url"], headers=headers)
    assert video.status_code == 200 and video.headers["content-type"] == "video/webm"
    assert video.content == WEBM

    # Someone else cannot read or overwrite it.
    intruder = auth_headers(api, other)
    assert api.get(done["video_url"], headers=intruder).status_code == 404
    assert (
        api.put(url, headers={**intruder, "Content-Type": "video/webm"}, content=WEBM).status_code
        == 404
    )
    listed = api.get(
        "/api/v1/studio/jobs", headers=headers, params={"property_id": str(listing.id)}
    ).json()
    assert [j["id"] for j in listed] == [job["id"]]
