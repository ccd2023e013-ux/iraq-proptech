"""The representative DEMO photo library: licences, credits and files."""

from __future__ import annotations

import io
import re

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import demo, demo_images
from app.demo_images import photo_caption, photo_library, pick_photo
from app.properties.models import Property

# Representative photos are credited to where they were published.
SOURCES = ("Wikimedia Commons", "Flickr")

FREE = re.compile(r"^(Public domain|CC0|CC BY(-SA)? (2\.0|2\.5|3\.0|4\.0))$")
DEMO_TYPES = ("HOUSE", "APARTMENT", "VILLA", "LAND", "SHOP", "OFFICE")


def test_every_photo_has_a_free_licence_and_a_full_credit() -> None:
    library = photo_library()
    assert len(library) >= 10
    for photo in library:
        assert FREE.match(photo.licence), photo
        assert photo.author.strip(), photo
        assert photo.source.startswith(
            ("https://commons.wikimedia.org/wiki/File:", "https://www.flickr.com/photos/")
        ), photo
        if photo.licence.startswith("CC BY"):
            assert photo.licence_url.startswith("https://creativecommons.org/licenses/"), photo


def test_photos_carry_no_metadata_and_are_web_sized() -> None:
    for photo in photo_library():
        image = Image.open(io.BytesIO(demo_images.photo_bytes(photo)))
        assert image.format == "JPEG"
        assert max(image.size) <= 1600
        assert not image.getexif(), f"{photo.file} still has EXIF metadata"


def test_each_demo_type_gets_a_photo_and_a_representative_caption() -> None:
    for code in DEMO_TYPES:
        photo = pick_photo(code, 7)
        assert photo is not None, code
        caption = photo_caption(photo)
        assert "صورة تمثيلية" in caption and "DEMO" in caption
        assert photo.licence in caption and len(caption) <= 200
    # Deterministic: the same listing seed always gets the same photo.
    assert pick_photo("HOUSE", 11) == pick_photo("HOUSE", 11)


@pytest.mark.db
def test_basra_seed_attaches_captioned_photos_only_when_asked(db_session: Session) -> None:
    demo.seed(db_session, listings=3, images=True)
    rows = (
        db_session.execute(select(Property).where(Property.title_ar.like("عقار تجريبي%")))
        .scalars()
        .all()
    )
    assert len(rows) == 3
    for p in rows:
        assert len(p.media) == 1
        caption = p.media[0].caption
        assert "صورة تمثيلية" in caption and any(s in caption for s in SOURCES)
        assert "تمثيلية" in p.description_ar and "representative" in p.description_en
