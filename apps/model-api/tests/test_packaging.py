import json
from pathlib import Path

import pytest

from scripts.package_models import REQUIRED_FILES, build_bundle


def _fake_artifacts(root: Path) -> Path:
    (root / "clean").mkdir(parents=True)
    (root / "models").mkdir(parents=True)

    for name in REQUIRED_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    for target, alpha in (("target_next_tmean_c", 10), ("target_next_tmean_c", 50)):
        (root / f"models/{target}_q{alpha}.json").write_text("{}", encoding="utf-8")

    # Build intermediates that must never be packaged.
    (root / "clean/training_table.parquet").write_text("x", encoding="utf-8")
    (root / "clean/X_features.npy").write_text("x", encoding="utf-8")
    (root / "clean/cleaned").mkdir()
    (root / "clean/cleaned/lahore.parquet").write_text("x", encoding="utf-8")
    return root


def test_build_bundle_copies_only_runtime_files(tmp_path) -> None:
    artifacts = _fake_artifacts(tmp_path / "artifacts")
    out = tmp_path / "model_store"

    manifest = build_bundle(artifacts, out)

    assert manifest["model_count"] == 2
    assert (out / "models/MANIFEST.json").exists() is False
    assert (out / "MANIFEST.json").exists()
    assert (out / "clean/seasonal_features.parquet").exists()
    assert (out / "models/target_next_tmean_c_q50.json").exists()

    # Training/build intermediates are excluded.
    assert not (out / "clean/training_table.parquet").exists()
    assert not (out / "clean/X_features.npy").exists()
    assert not (out / "clean/cleaned").exists()


def test_manifest_counts_match_files_on_disk(tmp_path) -> None:
    artifacts = _fake_artifacts(tmp_path / "artifacts")
    out = tmp_path / "model_store"

    manifest = build_bundle(artifacts, out)
    disk_files = [p for p in out.rglob("*") if p.is_file() and p.name != "MANIFEST.json"]

    assert manifest["file_count"] == len(disk_files)
    payload = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert payload["file_count"] == manifest["file_count"]


def test_build_bundle_requires_trained_models(tmp_path) -> None:
    artifacts = _fake_artifacts(tmp_path / "artifacts")
    for path in (artifacts / "models").glob("*_q*.json"):
        path.unlink()

    with pytest.raises(SystemExit):
        build_bundle(artifacts, tmp_path / "model_store")


def test_build_bundle_requires_artifacts_dir(tmp_path) -> None:
    with pytest.raises(SystemExit):
        build_bundle(tmp_path / "missing", tmp_path / "model_store")


def test_build_bundle_refuses_overwrite_without_force(tmp_path) -> None:
    artifacts = _fake_artifacts(tmp_path / "artifacts")
    out = tmp_path / "model_store"
    build_bundle(artifacts, out)

    with pytest.raises(SystemExit):
        build_bundle(artifacts, out)

    manifest = build_bundle(artifacts, out, force=True)
    assert manifest["model_count"] == 2
