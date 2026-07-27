"""Node 2b — wait for the reconstruction, then fetch the mesh.

Two durable strategies, both keyed on the committed serialize:
  * webhook push  — if PUBLIC_URL + webhook secret are configured, the node
    pauses via interrupt(); the KIRI webhook route resumes it with the model_url.
  * polling       — otherwise (and as the belt-and-suspenders fallback), poll
    getStatus until success, then download.
The KIRI download link expires in 60 minutes, so we fetch the mesh immediately
on success inside this node.
"""
from __future__ import annotations

import time

from langgraph.types import interrupt

from ...adapters.kiri import KiriClient, STATUS_SUCCESS, STATUS_FAILED, STATUS_EXPIRED
from ...config import get_settings
from ...storage import renders_dir
from ..state import ScanState

POLL_INTERVAL_S = 5.0
POLL_TIMEOUT_S = 900.0   # 15 min budget for a photo-scan job


def await_reconstruction(state: ScanState) -> dict:
    settings = get_settings()
    kiri = KiriClient(settings)
    serialize = state["serialize"]
    use_webhook = bool(settings.public_url and settings.kiri_webhook_secret)

    # --- resolve the download URL ---
    if use_webhook:
        # side-effect-free before interrupt(): pause until the webhook resumes.
        payload = interrupt({"awaiting": "kiri_reconstruction", "serialize": serialize})
        model_url = payload["model_url"] if isinstance(payload, dict) else payload
    else:
        deadline = time.monotonic() + POLL_TIMEOUT_S
        while True:
            status = kiri.get_status(serialize)
            if status == STATUS_SUCCESS:
                break
            if status in (STATUS_FAILED, STATUS_EXPIRED):
                return {"status": "reconstruction_failed",
                        "errors": [f"KIRI status {status} for {serialize}"]}
            if time.monotonic() > deadline:
                return {"status": "reconstruction_timeout",
                        "errors": [f"KIRI still processing after {POLL_TIMEOUT_S:.0f}s"]}
            time.sleep(POLL_INTERVAL_S)
        model_url = kiri.get_download_url(serialize)

    # --- fetch immediately (60-min link window) ---
    mesh_path = kiri.download_mesh(serialize, model_url, renders_dir(state["scan_id"]))
    return {"model_url": model_url, "mesh_path": mesh_path, "status": "mesh_ready"}
