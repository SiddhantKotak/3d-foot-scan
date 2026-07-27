"""Scan lifecycle endpoints: upload -> run -> progress(SSE) -> snapshot + assets."""
from __future__ import annotations

import json
import os
import uuid
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ..storage import renders_dir, uploads_dir
from ..graph.state import ScanState

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("")
async def create_scan(
    files: list[UploadFile] = File(...),
    foot_side: Literal["left", "right"] = Form(...),
    posture: Literal["weight_bearing", "non_weight_bearing"] = Form("non_weight_bearing"),
) -> dict:
    scan_id = uuid.uuid4().hex[:12]
    saved: list[str] = []
    for f in files:
        dest = os.path.join(uploads_dir(scan_id), os.path.basename(f.filename or "upload"))
        with open(dest, "wb") as out:
            out.write(await f.read())
        saved.append(dest)
    return {"scan_id": scan_id, "n_files": len(saved), "foot_side": foot_side, "posture": posture}


@router.post("/{scan_id}/run")
async def run_scan(scan_id: str, request: Request, foot_side: str = Form(...),
                   posture: str = Form("non_weight_bearing")) -> dict:
    up = uploads_dir(scan_id)
    images = [os.path.join(up, n) for n in sorted(os.listdir(up))]
    if not images:
        raise HTTPException(404, "no uploaded images for this scan")
    init: ScanState = {
        "scan_id": scan_id, "image_paths": images,
        "foot_side": foot_side, "posture": posture, "scale_hint": None, "errors": [],
    }
    request.app.state.runs.start(scan_id, init)
    return {"status": "started", "scan_id": scan_id, "n_images": len(images)}


@router.get("/{scan_id}/events")
async def scan_events(scan_id: str, request: Request) -> StreamingResponse:
    manager = request.app.state.runs

    def gen():
        for item in manager.events(scan_id):
            yield f"data: {json.dumps(item, default=str)}\n\n"
        yield "event: close\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{scan_id}")
async def scan_state(scan_id: str, request: Request) -> dict:
    return request.app.state.runs.snapshot(scan_id)


@router.get("/{scan_id}/history")
async def scan_history(scan_id: str, request: Request) -> dict:
    return {"history": request.app.state.runs.history(scan_id)}


@router.get("/{scan_id}/renders/{name}")
async def scan_render(scan_id: str, name: str) -> FileResponse:
    path = os.path.join(renders_dir(scan_id), os.path.basename(name))
    if not os.path.exists(path):
        raise HTTPException(404, "render not found")
    low = path.lower()
    if low.endswith((".jpg", ".jpeg")):
        media = "image/jpeg"
    elif low.endswith(".glb"):
        media = "model/gltf-binary"
    elif low.endswith(".gltf"):
        media = "model/gltf+json"
    elif low.endswith(".obj"):
        media = "text/plain"
    else:
        media = "image/png"
    return FileResponse(path, media_type=media)
