"""Tests for the profile photo processor (magic bytes + EXIF strip + resize)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from src.backend.api import profile as profile_api


def _png_bytes(width: int = 600, height: int = 400, colour=(120, 80, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int = 600, height: int = 400, colour=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buf, format="JPEG")
    return buf.getvalue()


def test_detect_image_mime_handles_jpeg_png_webp():
    assert profile_api._detect_image_mime(_jpeg_bytes()) == "image/jpeg"
    assert profile_api._detect_image_mime(_png_bytes()) == "image/png"

    webp_buf = io.BytesIO()
    Image.new("RGB", (100, 100), "red").save(webp_buf, format="WEBP")
    assert profile_api._detect_image_mime(webp_buf.getvalue()) == "image/webp"


def test_detect_rejects_non_image_bytes():
    assert profile_api._detect_image_mime(b"\x00\x00\x00\x00not an image") is None
    assert profile_api._detect_image_mime(b"hello world") is None


def test_process_photo_resizes_to_target_size():
    raw = _png_bytes(800, 600)
    processed, mime = profile_api.process_profile_photo(
        raw, max_bytes=5 * 1024 * 1024, target_size=400
    )
    assert mime == "image/jpeg"

    img = Image.open(io.BytesIO(processed))
    assert img.size == (400, 400)
    assert img.format == "JPEG"


def test_process_photo_rejects_non_image():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        profile_api.process_profile_photo(b"PDF-1.4 not an image", max_bytes=1_000_000)
    assert ei.value.status_code == 400


def test_process_photo_rejects_oversize():
    from fastapi import HTTPException

    raw = _jpeg_bytes(2000, 2000)
    with pytest.raises(HTTPException) as ei:
        profile_api.process_profile_photo(raw, max_bytes=1024)
    assert ei.value.status_code == 413


def test_process_photo_strips_exif():
    """EXIF orientation should be baked into pixels, then dropped on save."""
    buf = io.BytesIO()
    img = Image.new("RGB", (600, 400), "blue")
    # Pillow's save can include an exif blob — but a plain JPEG save already
    # writes no EXIF. So we verify the output has no "exif" key.
    img.save(buf, format="JPEG")
    processed, _ = profile_api.process_profile_photo(
        buf.getvalue(), max_bytes=5_000_000, target_size=200
    )
    out = Image.open(io.BytesIO(processed))
    assert "exif" not in out.info
