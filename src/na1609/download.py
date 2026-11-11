"""Explicit Copernicus 1-degree tile locator/downloader with no background activity."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

from .geo import validate_bbox

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"


def tile_urls(bbox: list[float] | tuple[float, ...]) -> list[str]:
    west, south, east, north = validate_bbox(bbox)
    urls = []
    for latitude in range(math.floor(south), math.ceil(north)):
        for longitude in range(math.floor(west), math.ceil(east)):
            lat = f"{'N' if latitude >= 0 else 'S'}{abs(latitude):02d}_00"
            lon = f"{'E' if longitude >= 0 else 'W'}{abs(longitude):03d}_00"
            name = f"Copernicus_DSM_COG_10_{lat}_{lon}_DEM"
            urls.append(f"{BUCKET}/{name}/{name}.tif")
    return urls


def download_tiles(bbox: list[float], destination: Path, *, dry_run: bool = False) -> list[Path]:
    urls = tile_urls(bbox)
    if len(urls) > 12:
        raise ValueError("pilot download capped at 12 one-degree tiles")
    if dry_run:
        for url in urls:
            print(url)
        return []
    destination.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for url in urls:
        out = destination / url.rsplit("/", 1)[-1]
        if not out.exists():
            temp = out.with_suffix(out.suffix + ".partial")
            try:
                with urlopen(Request(url, headers={"User-Agent": "NA1609-research/0.1"}), timeout=90) as response:
                    with temp.open("wb") as stream:
                        while chunk := response.read(1024 * 1024):
                            stream.write(chunk)
                temp.replace(out)
            except Exception:
                temp.unlink(missing_ok=True)
                raise
        downloaded.append(out)
    return downloaded
