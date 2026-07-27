"""Bridge the LangGraph run to the web layer.

Runs graph.stream() on a background thread and pushes per-node updates onto a
per-scan queue that the SSE endpoint drains. The stream stays logically open
across the review interrupt: the run thread posts an 'interrupt' event and
stops; a later resume thread posts more events to the SAME queue and finally a
'done' event that closes the SSE.
"""
from __future__ import annotations

import queue
import threading
from typing import Any

from langgraph.types import Command

from ..storage import write_json
from .build import build_graph, make_checkpointer
from .state import ScanState

_CLOSE = object()


class RunManager:
    def __init__(self) -> None:
        self.graph = build_graph(make_checkpointer())
        self._queues: dict[str, queue.Queue] = {}

    def _q(self, scan_id: str) -> queue.Queue:
        return self._queues.setdefault(scan_id, queue.Queue())

    def _config(self, scan_id: str) -> dict:
        return {"configurable": {"thread_id": scan_id}}

    # --- state access ---
    def snapshot(self, scan_id: str) -> dict[str, Any]:
        snap = self.graph.get_state(self._config(scan_id))
        return {"values": snap.values, "next": list(snap.next)}

    def history(self, scan_id: str) -> list[dict]:
        """Audit trail: every checkpointed super-step."""
        out = []
        for st in self.graph.get_state_history(self._config(scan_id)):
            out.append({"next": list(st.next),
                        "status": st.values.get("status"),
                        "step": st.metadata.get("step") if st.metadata else None})
        return out

    # --- driving the graph ---
    def _drive(self, scan_id: str, payload: Any) -> None:
        q = self._q(scan_id)
        config = self._config(scan_id)
        try:
            for chunk in self.graph.stream(payload, config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    intr = chunk["__interrupt__"][0]
                    q.put({"event": "interrupt", "payload": _safe(intr.value)})
                    return  # pause; a resume will continue on this same queue
                for node, partial in chunk.items():
                    q.put({"event": "node", "node": node, "data": _safe(partial)})
            values = self.graph.get_state(config).values
            write_json(scan_id, "final_state.json", _safe(values))
            q.put({"event": "done", "state": _safe(values)})
        except Exception as e:  # pragma: no cover - surfaced to the client
            q.put({"event": "error", "message": str(e)})
        finally:
            if not self._awaiting_review(scan_id):
                q.put(_CLOSE)

    def _awaiting_review(self, scan_id: str) -> bool:
        return bool(self.graph.get_state(self._config(scan_id)).next)

    def start(self, scan_id: str, init: ScanState) -> None:
        threading.Thread(target=self._drive, args=(scan_id, init), daemon=True).start()

    def resume(self, scan_id: str, decision: dict) -> None:
        threading.Thread(target=self._drive, args=(scan_id, Command(resume=decision)), daemon=True).start()

    def resume_reconstruction(self, scan_id: str, model_url: str) -> None:
        """Webhook-driven resume of the await_reconstruction interrupt."""
        threading.Thread(target=self._drive, args=(scan_id, Command(resume={"model_url": model_url})),
                         daemon=True).start()

    # --- SSE ---
    def events(self, scan_id: str):
        q = self._q(scan_id)
        while True:
            item = q.get()
            if item is _CLOSE:
                break
            yield item


def _safe(obj: Any) -> Any:
    """Make LangGraph values JSON-serialisable (drop non-serialisable extras)."""
    import json
    return json.loads(json.dumps(obj, default=str))
