"""Validation and processing of uploaded files.

The declared Content-Type is never trusted: formats are detected from the
bytes. Images are fully decoded and re-encoded, which strips EXIF metadata
(including GPS coordinates that could reveal an owner's exact address) and
neutralizes malformed or polyglot files.
"""

from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import AppError

MAX_PIXELS = 50_000_000  # reject decompression bombs
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
MAIN_MAX_SIDE = 2048
THUMB_MAX_SIDE = 480
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class UploadRejected(AppError):
    status_code = 415
    code = "UNSUPPORTED_FILE"


class UploadTooLarge(AppError):
    status_code = 413
    code = "FILE_TOO_LARGE"


@dataclass(frozen=True)
class ProcessedImage:
    main: bytes
    thumbnail: bytes
    width: int
    height: int
    sha256: str
    perceptual_hash: int
    content_type: str = "image/webp"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_size(data: bytes, limit: int) -> None:
    if len(data) == 0:
        raise UploadRejected("Empty file", code="EMPTY_FILE")
    if len(data) > limit:
        raise UploadTooLarge(
            "File is too large", details={"max_bytes": limit, "size_bytes": len(data)}
        )


def _open_image(data: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))
            fmt = probe.format
            probe.verify()  # structural check; the object is unusable afterwards
            image = Image.open(io.BytesIO(data))
            image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise UploadRejected("File is not a supported image") from exc
    except Image.DecompressionBombWarning as exc:
        raise UploadRejected("Image dimensions are too large") from exc
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise UploadRejected("Only JPEG, PNG and WebP images are accepted")
    return image


def difference_hash(image: Image.Image) -> int:
    """64-bit dHash: robust to resizing/re-compression, used for duplicate detection."""
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = small.tobytes()  # 72 grayscale bytes, row-major
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    # Store as signed 64-bit for PostgreSQL BIGINT.
    return bits - (1 << 64) if bits >= (1 << 63) else bits


def hamming_distance(a: int, b: int) -> int:
    return ((a ^ b) & ((1 << 64) - 1)).bit_count()


def _encode_webp(image: Image.Image, max_side: int, quality: int) -> tuple[bytes, int, int]:
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    copy.save(buffer, format="WEBP", quality=quality, method=4)
    return buffer.getvalue(), copy.width, copy.height


def process_image(data: bytes, *, limit: int) -> ProcessedImage:
    ensure_size(data, limit)
    image = _open_image(data)
    image = ImageOps.exif_transpose(image)  # honour orientation, then EXIF is dropped
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    main, width, height = _encode_webp(image, MAIN_MAX_SIDE, 82)
    thumb, _, _ = _encode_webp(image, THUMB_MAX_SIDE, 75)
    return ProcessedImage(
        main=main,
        thumbnail=thumb,
        width=width,
        height=height,
        sha256=sha256_hex(data),
        perceptual_hash=difference_hash(image),
    )


def sniff_document(data: bytes, *, limit: int) -> str:
    """Return the detected MIME type of an allowed private document."""
    ensure_size(data, limit)
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    try:
        image = _open_image(data)
    except UploadRejected as exc:
        raise UploadRejected("Documents must be PDF, JPEG, PNG or WebP") from exc
    return {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image.format or ""]


def sniff_video(data: bytes, *, limit: int) -> str:
    ensure_size(data, limit)
    if len(data) > 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    raise UploadRejected("Videos must be MP4 or WebM")


def safe_filename(name: str | None, fallback: str) -> str:
    """Display-only filename (never used as a storage path)."""
    if not name:
        return fallback
    cleaned = "".join(c for c in name if c.isalnum() or c in " ._-()").strip(" .")
    return cleaned[:150] or fallback
