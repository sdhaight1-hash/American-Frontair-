"""Acquire a published historical map scan without asserting georeferencing.

The NYPL's 1909 MacCoun scan depicts an interpretation of Manhattan in 1609.
Downloading it supplies an archival *source*, NOT a 1609 shoreline or DEM.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, UnidentifiedImageError

SOURCE_ID = "nypl_maccoun_1909_manhattan"
SOURCE_PAGE = "https://old-digitalcollections.nypl.org/items/97ee6342-cec2-2699-e040-e00a18067566"
IMAGE_ID = "ps_map_cd3_36"
IMAGE_URLS = {
    "preview": "https://images.nypl.org/index.php?download=1&id=ps_map_cd3_36&suffix=97ee6342-cec2-2699-e040-e00a18067566.001&t=w",
    "original": "https://iiif-prod.nypl.org/index.php?id=ps_map_cd3_36&t=g",
}
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
MIN_RESEARCH_LONG_AXIS = 3000


def _fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "NorthAmerica1609-archival-research/0.1"})
    with urlopen(request, timeout=120) as response:
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_DOWNLOAD_BYTES:
            raise ValueError("archival source exceeds download limit")
        chunks, total = [], 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise ValueError("archival source exceeds download limit")
            chunks.append(chunk)
        return b"".join(chunks)


def acquire_maccoun_map(output: Path, *, quality: str = "original", fetch=None) -> dict:
    """Persist an original or preview image and deterministic provenance manifest.

    Never silently fall back from original to preview: a lower-resolution image
    must be visible in metadata and cannot pass the digitization-readiness gate.
    """
    if quality not in IMAGE_URLS:
        raise ValueError("quality must be 'original' or 'preview'")
    output = Path(output)
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite an archived historical source")
    blob = (fetch or _fetch_bytes)(IMAGE_URLS[quality])
    if not isinstance(blob, bytes) or len(blob) < 100:
        raise ValueError("archival image response is missing or too short")
    if len(blob) > MAX_DOWNLOAD_BYTES:
        raise ValueError("archival source exceeds download limit")
    try:
        with Image.open(io.BytesIO(blob)) as image:
            image.verify()
        with Image.open(io.BytesIO(blob)) as image:
            width, height = image.size
            format_name = image.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("remote archive did not return a valid raster image") from exc
    if format_name not in ("JPEG", "PNG", "TIFF") or width < 100 or height < 100:
        raise ValueError("unsupported or unusable historical image")
    if (format_name == "JPEG" and output.suffix.lower() not in (".jpg", ".jpeg")) or (format_name == "PNG" and output.suffix.lower() != ".png") or (format_name == "TIFF" and output.suffix.lower() not in (".tif", ".tiff")):
        raise ValueError("file extension does not match source raster format")
    sha = hashlib.sha256(blob).hexdigest()
    ready = max(width, height) >= MIN_RESEARCH_LONG_AXIS and quality == "original"
    manifest = {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "source_image_id": IMAGE_ID,
        "source_page": SOURCE_PAGE,
        "download_url": IMAGE_URLS[quality],
        "source_creator": "Townsend MacCoun",
        "publication_year": 1909,
        "depicted_year": 1609,
        "source_kind": "retrospective_historical_cartography",
        "role": "archival_source_scan_not_georeferenced",
        "is_1609_reconstruction": False,
        "quality_requested": quality,
        "image_file": output.name,
        "image_format": format_name,
        "width_px": width,
        "height_px": height,
        "file_size_bytes": len(blob),
        "image_sha256": sha,
        "eligible_for_precision_tracing_review": ready,
        "tracing_gate": "image_quality_only_not_georeferenced" if ready else "insufficient_image_resolution_or_preview",
        "rights": "NYPL believes this item is public domain under US law; check non-US use separately.",
        "limitations": [
            "Retrospective 1909 reconstruction, not an eyewitness observation or survey in 1609.",
            "No control points, registered coordinates, historical shoreline geometries or uncertainty estimates included.",
            "Image size alone does not establish geographic or cartographic accuracy.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".partial")
    temp_meta = manifest_path.with_name(manifest_path.name + ".partial")
    try:
        if temp.exists() or temp_meta.exists():
            raise FileExistsError("stale partial archival download must be inspected")
        temp.write_bytes(blob)
        temp_meta.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(output)
        temp_meta.replace(manifest_path)
    finally:
        temp.unlink(missing_ok=True)
        temp_meta.unlink(missing_ok=True)
    return manifest


def inspect_archival_map(path: Path) -> dict:
    """Verify source bytes against the archived manifest before digitization."""
    path = Path(path)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if manifest.get("role") != "archival_source_scan_not_georeferenced" or manifest.get("source_id") != SOURCE_ID:
        raise ValueError("archive manifest has an unsupported source/role")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest.get("image_sha256"):
        raise ValueError("archival image integrity check failed")
    with Image.open(io.BytesIO(data)) as im:
        if list(im.size) != [manifest.get("width_px"), manifest.get("height_px")]:
            raise ValueError("archival image dimensions differ from manifest")
        im.verify()
    return manifest
