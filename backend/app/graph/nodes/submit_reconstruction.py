"""Node 2a — submit the reconstruction job to KIRI.

Deliberately split from the await node: this node COMMITS the KIRI serialize to
the checkpoint. If we submitted-and-waited in one node, a resume would re-run the
node top and re-submit (double billing). Submit here, wait there.
"""
from __future__ import annotations

from ...adapters.kiri import KiriClient
from ...config import get_settings
from ...storage import map_serialize
from ..state import ScanState


def submit_reconstruction(state: ScanState) -> dict:
    settings = get_settings()
    kiri = KiriClient(settings)
    serialize = kiri.submit_photo_scan(state["image_paths"], file_format="obj")
    map_serialize(serialize, state["scan_id"])   # for webhook -> thread_id resume
    return {
        "serialize": serialize,
        "status": "reconstruction_submitted" + ("" if kiri.live else " (mock)"),
    }
