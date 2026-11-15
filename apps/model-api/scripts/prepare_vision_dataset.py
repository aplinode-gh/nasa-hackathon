"""Clean and standardize vision image datasets using NumPy and Pandas.

- Scans image files under input directories (e.g. datasets/vision/disease/raw, nasa/*)
- Validates readability, removes corrupt/duplicate/tiny images
- Normalizes to RGB JPEG at a target size
- Emits cleaned images, labels.csv (for labeled disease folders), and a quality report

Designed to work with NumPy/Pandas + Pillow when available; falls back to basic
byte-level checks if Pillow is not installed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

try:
    from PIL import Image

    PIL_OK = True
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    PIL_OK = False

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _iter_images(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and f.suffix.lower() in IMG_EXTS:
                    yield f


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _infer_label(path: Path, root: Path) -> str | None:
    try:
        rel = path.relative_to(root)
    except Exception:
        return None
    parts = rel.parts
    # expect .../raw/<label>/file or .../<label>/file
    if len(parts) >= 2:
        # skip common container dirs
        skip = {"raw", "images", "img", "train", "test", "val", "processed"}
        if parts[0].lower() in skip and len(parts) >= 3:
            return parts[1]
        if parts[0].lower() not in skip:
            return parts[0]
    return None


def clean_images(
    inputs: list[Path],
    out_dir: Path,
    label_root: Path | None,
    size: int = 224,
    min_bytes: int = 1500,
    min_side: int = 32,
    quality: int = 90,
    limit: int | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    seen_hashes: set[str] = set()
    errors: list[dict] = []

    files = list(_iter_images(inputs))
    if limit:
        files = files[:limit]

    for idx, src in enumerate(files, 1):
        rec: dict = {
            "source_path": str(src),
            "source_name": src.name,
            "status": "pending",
        }
        try:
            data = src.read_bytes()
            rec["bytes_in"] = len(data)
            if len(data) < min_bytes:
                rec.update({"status": "rejected", "reason": "too_small_bytes"})
                records.append(rec)
                continue
            file_hash = _sha256_bytes(data)
            rec["sha256"] = file_hash
            if file_hash in seen_hashes:
                rec.update({"status": "rejected", "reason": "duplicate"})
                records.append(rec)
                continue

            label = _infer_label(src, label_root) if label_root else None
            rec["label"] = label

            if PIL_OK:
                try:
                    with Image.open(io.BytesIO(data)) as im:
                        im.load()
                        w, hgt = im.size
                        mode = im.mode
                        rec.update({"width": w, "height": hgt, "mode": mode})
                        if min(w, hgt) < min_side:
                            rec.update({"status": "rejected", "reason": "too_small_dims"})
                            records.append(rec)
                            continue
                        # normalize
                        im = im.convert("RGB")
                        resample = getattr(Image, "Resampling", Image).BILINEAR if hasattr(getattr(Image, "Resampling", Image), "BILINEAR") else 2
                        im = im.resize((size, size), resample)
                        arr = np.asarray(im, dtype=np.uint8)
                        # basic quality checks
                        rec["mean_px"] = float(arr.mean())
                        rec["std_px"] = float(arr.std())
                        if rec["std_px"] < 2.0:
                            rec.update({"status": "rejected", "reason": "near_uniform"})
                            records.append(rec)
                            continue
                        # save
                        sub = label if label else "unlabeled"
                        safe_stem = hashlib.sha1(file_hash.encode("utf-8")).hexdigest()[:16]
                        dst = out_dir / sub / f"{safe_stem}.jpg"
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        im.save(dst, format="JPEG", quality=quality, optimize=True)
                        out_bytes = dst.stat().st_size
                except Exception as e:
                    rec.update({"status": "rejected", "reason": f"decode_error:{type(e).__name__}:{e}"})
                    records.append(rec)
                    continue
            else:
                # No Pillow: basic signature check and copy-as-is
                is_jpg = data[:2] == b"\xff\xd8"
                is_png = data[:8].startswith(b"\x89PNG\r\n\x1a\n")
                if not (is_jpg or is_png):
                    rec.update({"status": "rejected", "reason": "unsupported_without_pillow"})
                    records.append(rec)
                    continue
                sub = label if label else "unlabeled"
                ext = ".jpg" if is_jpg else ".png"
                safe_stem = hashlib.sha1(file_hash.encode("utf-8")).hexdigest()[:16]
                dst = out_dir / sub / f"{safe_stem}{ext}"
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                out_bytes = len(data)

            seen_hashes.add(file_hash)
            rec.update(
                {
                    "status": "ok",
                    "output_path": str(dst),
                    "bytes_out": int(out_bytes),
                    "label_inferred": label,
                }
            )
            records.append(rec)
        except Exception as e:
            rec.update({"status": "error", "reason": str(e)})
            records.append(rec)
            errors.append({"path": str(src), "error": str(e)})

        if idx % 500 == 0:
            print(f"processed {idx}/{len(files)}")

    df = pd.DataFrame(records)
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pillow_available": PIL_OK,
        "input_count": int(len(df)) if not df.empty else 0,
        "ok": int((df["status"] == "ok").sum()) if not df.empty else 0,
        "rejected": int((df["status"] == "rejected").sum()) if not df.empty else 0,
        "errors": int((df["status"] == "error").sum()) if not df.empty else 0,
        "params": {"size": size, "min_bytes": min_bytes, "min_side": min_side, "quality": quality},
    }

    if not df.empty and "label" in df.columns:
        ok_df = df[df["status"] == "ok"].copy()
        if not ok_df.empty:
            label_counts = ok_df["label"].fillna("unlabeled").value_counts().sort_index()
            report["label_counts"] = {str(k): int(v) for k, v in label_counts.items()}
            # labels.csv for downstream training
            labels_csv = out_dir / "labels.csv"
            out_labels = ok_df[["output_path", "label", "sha256", "bytes_out"]].copy()
            out_labels["label"] = out_labels["label"].fillna("unlabeled")
            out_labels.to_csv(labels_csv, index=False)
            report["labels_csv"] = str(labels_csv)

        # numeric summary via pandas/numpy
        num_cols = [c for c in ["bytes_in", "bytes_out", "width", "height", "mean_px", "std_px"] if c in ok_df.columns]
        if num_cols:
            desc = ok_df[num_cols].describe().replace({np.nan: None})
            report["numeric_summary"] = json.loads(desc.to_json())

    index_path = out_dir / "index.csv"
    report_path = out_dir / "quality_report.json"
    df.to_csv(index_path, index=False)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["index_csv"] = str(index_path)
    report["quality_report"] = str(report_path)
    print(json.dumps({k: report[k] for k in ["input_count", "ok", "rejected", "errors", "pillow_available"]}, indent=2))
    if "label_counts" in report:
        print("labels:", report["label_counts"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inputs", nargs="+", required=True, help="Input files/dirs to scan")
    ap.add_argument("--out", required=True, help="Output directory for cleaned images")
    ap.add_argument("--label-root", default=None, help="Root dir used to infer labels from subfolders")
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--min-bytes", type=int, default=1500)
    ap.add_argument("--min-side", type=int, default=32)
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    inputs = [Path(p) for p in args.inputs]
    out_dir = Path(args.out)
    label_root = Path(args.label_root) if args.label_root else (inputs[0] if len(inputs) == 1 and inputs[0].is_dir() else None)
    clean_images(
        inputs=inputs,
        out_dir=out_dir,
        label_root=label_root,
        size=args.size,
        min_bytes=args.min_bytes,
        min_side=args.min_side,
        quality=args.quality,
        limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
