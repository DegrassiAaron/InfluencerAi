"""Utilities to bootstrap required model checkpoints."""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict

import requests

# Mapping of model-relative paths (from the repository root) to their metadata.
MODEL_SPECS: Dict[str, Dict[str, str]] = {
    "models/base/sdxl.safetensors": {
        "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        # Extracted from the upstream object metadata (x-linked-etag header).
        "sha256": "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b",
        "size_bytes": "6938078334",
    },
}

CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _repo_root() -> Path:
    """Return the absolute path to the repository root."""
    return Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    """Compute the SHA256 checksum of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _download(url: str, destination: Path) -> Path:
    """Download a URL to a temporary file in the destination directory."""
    headers = {}
    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(url, stream=True, headers=headers, timeout=60)
    response.raise_for_status()

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent) as tmp:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                tmp.write(chunk)
        tmp_path = Path(tmp.name)

    return tmp_path


def _ensure_file(path: Path, spec: Dict[str, str]) -> None:
    """Ensure a file exists at the given path with the expected checksum."""
    expected_sha = spec.get("sha256")
    if path.exists():
        if expected_sha is None:
            print(f"✔ {path} already exists; skipping checksum validation.")
            return
        current_sha = _sha256(path)
        if current_sha == expected_sha:
            print(f"✔ {path} already present (sha256 ok).")
            return
        print(
            f"! {path} exists but checksum mismatch (expected {expected_sha}, got {current_sha}).\n"
            "  Re-downloading…"
        )
        path.unlink()

    print(f"↓ Downloading {path}…")
    tmp_path = _download(spec["url"], path)

    if expected_sha:
        actual_sha = _sha256(tmp_path)
        if actual_sha != expected_sha:
            tmp_path.unlink(missing_ok=True)
            raise ValueError(
                f"Checksum mismatch for {path}: expected {expected_sha}, got {actual_sha}."
            )
    shutil.move(str(tmp_path), str(path))
    print(f"✓ Downloaded {path} ({path.stat().st_size / (1024 ** 3):.2f} GiB).")


def ensure_models(model_specs: Dict[str, Dict[str, str]] | None = None) -> None:
    """Ensure all required model artifacts are present on disk.

    Args:
        model_specs: Optional override for the models to ensure. Defaults to
            :data:`MODEL_SPECS`.
    """
    specs = model_specs or MODEL_SPECS
    root = _repo_root()

    for relative_path, spec in specs.items():
        target = root / relative_path
        _ensure_file(target, spec)


if __name__ == "__main__":  # pragma: no cover
    try:
        ensure_models()
    except KeyboardInterrupt:
        print("Download interrupted by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # Surface errors with non-zero exit.
        print(f"Error while bootstrapping models: {exc}", file=sys.stderr)
        sys.exit(1)
