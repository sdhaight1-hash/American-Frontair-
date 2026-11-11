"""Standard-library primitives shared by the offline world reader and GIS exporter."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_bbox(bbox) -> tuple[float, float, float, float]:
    if len(bbox) != 4 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in bbox):
        raise ValueError("bbox must contain finite west,south,east,north coordinates")
    w, s, e, n = map(float, bbox)
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("invalid WGS84 geographic bbox")
    return w, s, e, n


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".partial")
    try:
        temp.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
