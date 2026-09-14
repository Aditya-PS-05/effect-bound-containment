"""Logical archived-source names and their current on-disk locations.

Evidence archives record sources under stable logical names ("run_local_sandbox.py",
"src/local_service.py") so that old and new archives share the same keys. When the
runners moved under experiments/ in the repository reorganisation, no frozen archive
was touched; this resolver maps a logical name to the file's current location.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source_path(name):
    """Current file for a logical source name (root first, then experiments/)."""
    direct = ROOT / name
    if direct.exists():
        return direct
    moved = ROOT / "experiments" / name
    return moved if moved.exists() else direct


def logical_name(path):
    """Stable archive key for a current file (inverse of source_path)."""
    rel = Path(path).resolve().relative_to(ROOT).as_posix()
    return rel[len("experiments/"):] if rel.startswith("experiments/") else rel
