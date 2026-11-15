"""Collect NASA-sourced agricultural/Earth-observation imagery and metadata.

Sources (public endpoints):
- NASA Image and Video Library API (images-api.nasa.gov) for agriculture/crop/drought/soil imagery metadata and previews.
- NASA GIBS WMTS tiles (gibs.earthdata.nasa.gov) for MODIS/VIIRS corrected reflectance over Pakistan ag regions.
- NASA Worldview snapshot API (wvs.earthdata.nasa.gov) when accessible.

Outputs a manifest with per-asset provenance and download status under datasets/vision/nasa/.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = {"User-Agent": "fieldshift-nasa-vision-harvest/1.0 (+NASA Space Apps Field Shift)"}


def _get_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _download(url: str, out_path: Path, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            ctype = (r.headers.get("Content-Type") or "").lower()
        if len(data) < 1500:
            return {"ok": False, "error": "too_small", "bytes": len(data), "content_type": ctype, "url": url}
        is_image = data[:2] == b"\xff\xd8" or data[:8].startswith(b"\x89PNG") or "image" in ctype
        if not is_image:
            return {"ok": False, "error": "not_image", "bytes": len(data), "content_type": ctype, "url": url}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return {"ok": True, "bytes": len(data), "content_type": ctype, "url": url, "file": str(out_path)}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}


def _latlon_to_tile(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def harvest_library(out_dir: Path, max_items: int = 24) -> list[dict]:
    queries = [
        "agriculture satellite imagery",
        "crop drought NASA Earth observation",
        "soil moisture satellite",
        "Landsat farmland irrigation",
        "MODIS vegetation agriculture",
        "flood cropland satellite",
    ]
    seen: set[str] = set()
    items: list[dict] = []
    for q in queries:
        url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode(
            {"q": q, "media_type": "image", "page_size": 20}
        )
        try:
            payload = _get_json(url)
        except Exception as e:
            items.append({"query": q, "ok": False, "error": str(e)})
            continue
        for it in payload.get("collection", {}).get("items", []):
            data = (it.get("data") or [{}])[0]
            nasa_id = str(data.get("nasa_id") or "").strip()
            if not nasa_id or nasa_id in seen:
                continue
            seen.add(nasa_id)
            links = it.get("links") or []
            preview = ""
            for link in links:
                href = str(link.get("href") or "")
                if href:
                    preview = href
                    break
            rec = {
                "source": "nasa_image_library",
                "query": q,
                "nasa_id": nasa_id,
                "title": data.get("title"),
                "description": (data.get("description") or "")[:800],
                "date_created": data.get("date_created"),
                "center": data.get("center"),
                "keywords": data.get("keywords") or [],
                "preview_url": preview,
            }
            items.append(rec)
            if len([x for x in items if x.get("nasa_id")]) >= max_items:
                return items
        time.sleep(0.2)
    return items


def download_library_previews(items: list[dict], out_dir: Path, limit: int = 12) -> list[dict]:
    downloaded = 0
    for rec in items:
        if downloaded >= limit:
            break
        if not rec.get("nasa_id") or not rec.get("preview_url"):
            continue
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in rec["nasa_id"])[:80]
        ext = ".jpg"
        href = rec["preview_url"].lower()
        if ".png" in href:
            ext = ".png"
        path = out_dir / "library" / f"{safe}{ext}"
        if path.exists() and path.stat().st_size > 1500:
            rec.update({"file": str(path), "bytes": path.stat().st_size, "ok": True, "cached": True})
            downloaded += 1
            continue
        res = _download(rec["preview_url"], path)
        rec.update(res)
        if res.get("ok"):
            downloaded += 1
        time.sleep(0.25)
    return items


def harvest_gibs(out_dir: Path) -> list[dict]:
    sites = [
        ("lahore", 31.5204, 74.3587),
        ("multan", 30.1575, 71.5249),
        ("faisalabad", 31.4504, 73.1350),
        ("hyderabad", 25.3960, 68.3578),
        ("larkana", 27.5570, 68.2028),
        ("peshawar", 34.0151, 71.5249),
        ("quetta", 30.1798, 66.9750),
    ]
    dates = ["2023-08-15", "2024-02-10", "2024-05-20", "2024-09-15"]
    layers = [
        ("MODIS_Terra_CorrectedReflectance_TrueColor", "jpg"),
        ("VIIRS_NOAA20_CorrectedReflectance_TrueColor", "jpg"),
    ]
    records: list[dict] = []
    for name, lat, lon in sites:
        for date in dates:
            for layer, ext in layers:
                for z in (6, 7):
                    x, y = _latlon_to_tile(lat, lon, z)
                    url = (
                        f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/"
                        f"{date}/GoogleMapsCompatible_Level{z}/{y}/{x}.{ext}"
                    )
                    out = out_dir / "gibs" / f"{layer.split('_')[0].lower()}_{name}_{date}_z{z}_y{y}_x{x}.{ext}"
                    rec = {
                        "source": "nasa_gibs_wmts",
                        "site": name,
                        "lat": lat,
                        "lon": lon,
                        "date": date,
                        "layer": layer,
                        "z": z,
                        "x": x,
                        "y": y,
                    }
                    if out.exists() and out.stat().st_size > 1500:
                        rec.update({"ok": True, "cached": True, "file": str(out), "bytes": out.stat().st_size, "url": url})
                    else:
                        res = _download(url, out)
                        rec.update(res)
                    records.append(rec)
                    time.sleep(0.15)
    return records


def harvest_worldview(out_dir: Path) -> list[dict]:
    # Worldview snapshot v1; may be unavailable in some environments.
    regions = [
        ("punjab_central", "71.5,29.8,74.8,32.2"),
        ("sindh_irrigated", "67.5,24.8,69.5,27.8"),
        ("kp_valley", "71.0,33.5,73.0,35.0"),
    ]
    dates = ["2024-03-20", "2024-06-15", "2024-09-10"]
    layers = "MODIS_Terra_CorrectedReflectance_TrueColor,Coastlines_15m"
    records: list[dict] = []
    for name, bbox in regions:
        for date in dates:
            params = {
                "REQUEST": "GetSnapshot",
                "TIME": date,
                "BBOX": bbox,
                "CRS": "EPSG:4326",
                "LAYERS": layers,
                "FORMAT": "image/jpeg",
                "WIDTH": "512",
                "HEIGHT": "512",
            }
            url = "https://wvs.earthdata.nasa.gov/api/v1/snapshot?" + urllib.parse.urlencode(params)
            out = out_dir / "worldview" / f"{name}_{date}_modis.jpg"
            rec = {"source": "nasa_worldview_snapshot", "region": name, "date": date, "bbox": bbox, "layers": layers}
            if out.exists() and out.stat().st_size > 1500:
                rec.update({"ok": True, "cached": True, "file": str(out), "bytes": out.stat().st_size, "url": url})
            else:
                res = _download(url, out)
                rec.update(res)
            records.append(rec)
            time.sleep(0.3)
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="datasets/vision/nasa", help="Output directory")
    ap.add_argument("--skip-library", action="store_true")
    ap.add_argument("--skip-gibs", action="store_true")
    ap.add_argument("--skip-worldview", action="store_true")
    ap.add_argument("--max-library", type=int, default=24)
    ap.add_argument("--max-previews", type=int, default=12)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            "NASA Image and Video Library API (https://images-api.nasa.gov)",
            "NASA GIBS WMTS (https://gibs.earthdata.nasa.gov)",
            "NASA Worldview Snapshot (https://wvs.earthdata.nasa.gov/api/v1/snapshot)",
        ],
        "library": [],
        "gibs": [],
        "worldview": [],
    }

    if not args.skip_library:
        items = harvest_library(out_dir, max_items=args.max_library)
        manifest["library"] = download_library_previews(items, out_dir, limit=args.max_previews)
    if not args.skip_gibs:
        manifest["gibs"] = harvest_gibs(out_dir)
    if not args.skip_worldview:
        manifest["worldview"] = harvest_worldview(out_dir)

    def _count(records: list[dict]) -> dict:
        ok = sum(1 for r in records if r.get("ok"))
        return {"ok": ok, "total": len(records)}

    manifest["summary"] = {
        "library": _count(manifest["library"]),
        "gibs": _count(manifest["gibs"]),
        "worldview": _count(manifest["worldview"]),
    }

    out_path = out_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest["summary"], indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
