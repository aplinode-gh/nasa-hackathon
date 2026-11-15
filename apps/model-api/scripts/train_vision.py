from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.vision.model import (
    DISEASE_LABELS_CSV,
    NASA_LABELS_CSV,
    VISION_DIR,
    train_vision_model,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the vision (disease/context) model")
    parser.add_argument("--disease-labels", default=str(DISEASE_LABELS_CSV))
    parser.add_argument("--nasa-labels", default=str(NASA_LABELS_CSV))
    parser.add_argument("--out", default=str(VISION_DIR))
    parser.add_argument("--no-nasa", action="store_true", help="Train on disease labels only")
    args = parser.parse_args()

    csvs = [Path(args.disease_labels)]
    if not args.no_nasa and Path(args.nasa_labels).exists():
        csvs.append(Path(args.nasa_labels))

    meta = train_vision_model(label_csvs=csvs, out_dir=Path(args.out))
    print(json.dumps({
        "ok": True,
        "out": args.out,
        "num_samples": meta.get("num_samples"),
        "classes": meta.get("classes"),
        "accuracy": meta.get("accuracy"),
        "f1_weighted": meta.get("f1_weighted"),
        "label_counts": meta.get("label_counts"),
    }, indent=2))


if __name__ == "__main__":
    main()
