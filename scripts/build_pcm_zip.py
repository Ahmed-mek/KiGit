#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src" / "kigit"
PKG_DIR = REPO_ROOT / "packaging"
DIST_DIR = REPO_ROOT / "dist"
STAGE_DIR = REPO_ROOT / ".stage_pcm"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_metadata_template() -> dict:
    template_path = PKG_DIR / "metadata.in.json"
    with template_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_metadata(stage_root: Path, version: str) -> None:
    metadata = _load_metadata_template()
    versions = metadata.get("versions", [])
    if not versions:
        raise RuntimeError("packaging/metadata.in.json must include at least one versions[] entry")
    versions = list(versions)
    versions[0] = dict(versions[0])
    versions[0]["version"] = version
    metadata["versions"] = versions[:1]

    out_path = stage_root / "metadata.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_tree_flattened(stage_plugins: Path) -> None:
    stage_plugins.mkdir(parents=True, exist_ok=True)
    if not SRC_DIR.exists():
        raise RuntimeError(f"Missing source dir: {SRC_DIR}")

    for item in SRC_DIR.iterdir():
        if item.name in {"__pycache__"}:
            continue
        if item.is_dir():
            shutil.copytree(item, stage_plugins / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, stage_plugins / item.name)


def _copy_resources(stage_root: Path) -> None:
    icon = PKG_DIR / "icon.png"
    if not icon.exists():
        return
    res_dir = stage_root / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon, res_dir / "icon.png")


def build_zip(version: str, out_zip: Path) -> tuple[str, int]:
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    stage_plugins = STAGE_DIR / "plugins"
    _copy_tree_flattened(stage_plugins)
    _copy_resources(STAGE_DIR)
    _write_metadata(STAGE_DIR, version)

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()

    # Deterministic-ish ZIP: stable sort + fixed timestamps.
    fixed_date_time = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(STAGE_DIR.rglob("*")):
            if file_path.is_dir():
                continue
            arcname = file_path.relative_to(STAGE_DIR).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=fixed_date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            data = file_path.read_bytes()
            zf.writestr(info, data)

    size = out_zip.stat().st_size
    return _sha256_file(out_zip), size


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build a KiCad PCM-compatible ZIP for KiGit.")
    parser.add_argument("--version", required=True, help="Plugin version to embed into metadata.json")
    parser.add_argument(
        "--out",
        default=str(DIST_DIR / "kigit.zip"),
        help="Output ZIP path (default: dist/kigit.zip)",
    )
    args = parser.parse_args(argv)

    out_zip = Path(args.out).resolve()
    digest, size = build_zip(args.version, out_zip)
    print(f"Wrote: {out_zip}")
    print(f"sha256: {digest}")
    print(f"size: {size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

