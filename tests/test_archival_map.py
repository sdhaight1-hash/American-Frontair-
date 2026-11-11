"""Synthetic raster fixtures test provenance; no generated picture is a historic map."""
from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from na1609.archival_map import IMAGE_URLS, SOURCE_ID, acquire_maccoun_map, inspect_archival_map
from na1609.cli import main


def image_bytes(dimensions=(3400, 1600), fmt="JPEG"):
    stream = io.BytesIO()
    Image.new("RGB", dimensions, (220, 208, 180)).save(stream, format=fmt)
    return stream.getvalue()


def test_original_qualifies_for_image_review_but_not_1609_geometry(tmp_path):
    dest = tmp_path / "archival.jpg"
    m = acquire_maccoun_map(dest, quality="original", fetch=lambda url: image_bytes())
    assert m["eligible_for_precision_tracing_review"] is True
    assert m["is_1609_reconstruction"] is False
    assert m["role"] == "archival_source_scan_not_georeferenced"
    assert m["publication_year"] == 1909 and m["depicted_year"] == 1609
    assert m["source_id"] == SOURCE_ID
    assert inspect_archival_map(dest) == m
    assert m["width_px"] == 3400 and m["height_px"] == 1600


def test_preview_is_never_precision_ready_even_if_upscaled(tmp_path):
    dest = tmp_path / "preview.jpg"
    m = acquire_maccoun_map(dest, quality="preview", fetch=lambda url: image_bytes((4000, 1800)))
    assert m["eligible_for_precision_tracing_review"] is False
    assert m["tracing_gate"] == "insufficient_image_resolution_or_preview"


def test_low_resolution_original_is_not_ready(tmp_path):
    m = acquire_maccoun_map(tmp_path / "low.jpg", quality="original", fetch=lambda url: image_bytes((760, 213)))
    assert m["eligible_for_precision_tracing_review"] is False


def test_html_error_page_not_stored_as_map(tmp_path):
    dest = tmp_path / "map.jpg"
    with pytest.raises(ValueError, match="valid raster"):
        acquire_maccoun_map(dest, fetch=lambda url: b"<html>server error</html>" * 50)
    assert not dest.exists() and not dest.with_suffix(".manifest.json").exists()


def test_extension_mismatch_rejected_without_files(tmp_path):
    dest = tmp_path / "map.png"
    with pytest.raises(ValueError, match="extension"):
        acquire_maccoun_map(dest, fetch=lambda url: image_bytes())
    assert not dest.exists()


def test_archive_is_immutable_and_tampering_is_detected(tmp_path):
    dest = tmp_path / "scan.jpg"
    acquire_maccoun_map(dest, fetch=lambda url: image_bytes())
    with pytest.raises(FileExistsError, match="overwrite"):
        acquire_maccoun_map(dest, fetch=lambda url: image_bytes())
    dest.write_bytes(b"bad")
    with pytest.raises(ValueError, match="integrity"):
        inspect_archival_map(dest)


def test_invalid_tier_refused(tmp_path):
    with pytest.raises(ValueError, match="quality"):
        acquire_maccoun_map(tmp_path / "bad.jpg", quality="upscaled")


def test_cli_dry_run_does_not_fetch_or_write(tmp_path, capsys):
    dest = tmp_path / "preview.jpg"
    assert main(["fetch-archival-map", "--output", str(dest), "--quality", "preview", "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"url": IMAGE_URLS["preview"], "quality": "preview", "dry_run": True}
    assert not dest.exists()


def test_immutable_manifest_has_stable_content(tmp_path):
    first = tmp_path / "first" / "original.jpg"
    second = tmp_path / "second" / "original.jpg"
    payload = image_bytes()
    a = acquire_maccoun_map(first, fetch=lambda url: payload)
    b = acquire_maccoun_map(second, fetch=lambda url: payload)
    assert a == b
    assert first.read_bytes() == second.read_bytes()
