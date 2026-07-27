"""Local artifact storage + the KIRI serialize -> thread_id map.

PoC-simple: per-scan directories on disk and an in-process dict for the reverse
lookup a webhook needs (serialize -> thread_id). Swap for a DB row in
production; the interface stays the same.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .config import get_settings


def scan_dir(scan_id: str) -> str:
    d = os.path.join(get_settings().data_dir, scan_id)
    os.makedirs(d, exist_ok=True)
    return d


def uploads_dir(scan_id: str) -> str:
    d = os.path.join(scan_dir(scan_id), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def renders_dir(scan_id: str) -> str:
    d = os.path.join(scan_dir(scan_id), "renders")
    os.makedirs(d, exist_ok=True)
    return d


def write_json(scan_id: str, name: str, payload: dict[str, Any]) -> str:
    path = os.path.join(scan_dir(scan_id), name)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


# --- serialize (KIRI task id) <-> thread_id (== scan_id) reverse map ---
_SERIALIZE_TO_THREAD: dict[str, str] = {}


def map_serialize(serialize: str, thread_id: str) -> None:
    _SERIALIZE_TO_THREAD[serialize] = thread_id


def thread_for_serialize(serialize: str) -> str | None:
    return _SERIALIZE_TO_THREAD.get(serialize)
