"""Podiatrist review resume endpoint.

Resumes the review interrupt via Command(resume=decision) on the same thread_id.
New progress events flow to the existing SSE stream for this scan.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/scans", tags=["review"])


class ReviewDecision(BaseModel):
    approved: bool = True
    edits: dict = {}


@router.post("/{scan_id}/resume")
async def resume_review(scan_id: str, decision: ReviewDecision, request: Request) -> dict:
    request.app.state.runs.resume(scan_id, decision.model_dump())
    return {"status": "resumed", "scan_id": scan_id}
