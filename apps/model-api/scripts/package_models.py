from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"

# Exactly what the API opens at request time. Everything else in artifacts/
# is a build intermediate (raw POWER pulls, cleaned daily parquet, training
# matrices) and must not be shipped.
REQUIRED_FILES = [
    "clean/seasonal_features.parquet",
    "clean/long_term_trends.csv",
    "models/metrics.json",
    "models/calibration.json",
    "models/feature_spec.json",
    "models/target_spec.json",
]

# Optional multimodal vision artifacts (disease detection + image context).
VISION_FILES = [
    "vision/disease_model.joblib",
    "vision/disease_meta.json",
]


def _required_models(artifact_dir: Path) -> list[str]:
    models = sorted((artifact_dir / "models").glob("*_q*.json"))
    return [f"models/{path.name}" for path in models]


def build_bundle(artifact_dir: Path, out_dir: Path, force: bool = False) -> dict:
    if not artifact_dir.exists():
        raise SystemExit(
            f"Artifacts not found at {artifact_dir}. "
            "Run prepare_dataset.py and train_forecast.py first."
        )

    targets = _required_models(artifact_dir)
    if not targets:
        raise SystemExit(
            f"No trained models found in {artifact_dir / 'models'}. "
            "Run scripts/train_forecast.py first."
        )

    wanted = REQUIRED_FILES + targets
    # Vision is optional (multimodal disease/context model) but included when trained.
    for name in VISION_FILES:
        if (artifact_dir / name).exists():
            wanted.append(name)

    missing = [name for name in wanted if not (artifact_dir / name).exists()]
    if missing:
        raise SystemExit("Missing required artifacts:\n  " + "\n  ".join(missing))

    if out_dir.exists():
        if not force:
            raise SystemExit(f"{out_dir} already exists. Pass --force to replace it.")
        shutil.rmtree(out_dir)

    total = 0
    for name in wanted:
        source = artifact_dir / name
        destination = out_dir / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        total += destination.stat().st_size

    manifest = {
        "files": wanted,
        "file_count": len(wanted),
        "model_count": len(targets),
        "total_bytes": total,
        "total_mb": round(total / 1e6, 2),
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package the runtime-required model artifacts for deployment"
    )
    parser.add_argument("--artifacts", default=str(ARTIFACT_DIR))
    parser.add_argument("--out", default="model_store")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = build_bundle(Path(args.artifacts), Path(args.out), args.force)
    print(f"Wrote model bundle to {args.out}")
    print(f"  {manifest['file_count']} files "
          f"({manifest['model_count']} models), {manifest['total_mb']} MB")
    for name in manifest["files"]:
        print(f"    {name}")


if __name__ == "__main__":
    main()
