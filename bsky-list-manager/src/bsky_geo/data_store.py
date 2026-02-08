"""JSON file CRUD for config, members, and candidates."""

from __future__ import annotations

import fcntl
import json
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def ensure_data_dir() -> None:
    """Create data directory and subdirectories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "crawl_cache").mkdir(exist_ok=True)
    (DATA_DIR / "backups").mkdir(exist_ok=True)


@contextmanager
def _locked_file(path: Path, mode: str = "r"):
    """Context manager that acquires an exclusive lock on a file."""
    f = open(path, mode)
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield f
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file, returning empty dict if it doesn't exist."""
    if not path.exists():
        return {}
    with _locked_file(path, "r") as f:
        content = f.read()
        if not content.strip():
            return {}
        return json.loads(content)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    """Write data to a JSON file with exclusive lock."""
    ensure_data_dir()
    with _locked_file(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")


# --- Config ---

def config_path() -> Path:
    return DATA_DIR / "config.json"


def load_config() -> dict[str, Any]:
    return _load_json(config_path())


def save_config(data: dict[str, Any]) -> None:
    _save_json(config_path(), data)


# --- Members ---

def members_path() -> Path:
    return DATA_DIR / "members.json"


def load_members() -> dict[str, Any]:
    """Load members dict keyed by DID."""
    return _load_json(members_path())


def save_members(data: dict[str, Any]) -> None:
    _save_json(members_path(), data)


# --- Candidates ---

def candidates_path() -> Path:
    return DATA_DIR / "candidates.json"


def load_candidates() -> dict[str, Any]:
    """Load candidates dict keyed by DID."""
    return _load_json(candidates_path())


def save_candidates(data: dict[str, Any]) -> None:
    _save_json(candidates_path(), data)


# --- Crawl Cache ---

def crawl_cache_path(did: str) -> Path:
    """Path for a cached crawl result for a specific DID."""
    safe_name = did.replace(":", "_")
    return DATA_DIR / "crawl_cache" / f"{safe_name}.json"


def load_crawl_cache(did: str) -> dict[str, Any] | None:
    """Load cached crawl data for a DID, or None if not cached."""
    path = crawl_cache_path(did)
    if not path.exists():
        return None
    data = _load_json(path)
    return data if data else None


def save_crawl_cache(did: str, data: dict[str, Any]) -> None:
    """Save crawl data for a DID."""
    ensure_data_dir()
    _save_json(crawl_cache_path(did), data)


# --- Backup ---

def backup(filename: str) -> Path | None:
    """Create a timestamped backup of a data file before mutations.

    Args:
        filename: Name of file in data/ to back up (e.g. "members.json")

    Returns:
        Path to backup file, or None if source doesn't exist.
    """
    source = DATA_DIR / filename
    if not source.exists():
        return None
    ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = source.stem
    suffix = source.suffix
    backup_path = DATA_DIR / "backups" / f"{stem}_{ts}{suffix}"
    shutil.copy2(source, backup_path)
    return backup_path
