"""Assemble the LangGraph pipeline (the orchestration spine).

Flow:
  START -> quality_gate --(rejected)--> END
                        \--(passed)--> submit_reconstruction -> await_reconstruction
        -> measure -> vision_read -> review --(interrupt: podiatrist)--> END

The SQLite checkpointer persists state after every node keyed by thread_id
(== scan_id), giving crash-resume, the review interrupt, and a full audit trail
(get_state_history) for free.
"""
from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END

from ..config import get_settings
from .nodes.await_reconstruction import await_reconstruction
from .nodes.measure import measure
from .nodes.quality_gate import quality_gate, route_after_quality
from .nodes.review import review
from .nodes.submit_reconstruction import submit_reconstruction
from .nodes.vision_read import vision_read
from .state import ScanState


def build_graph(checkpointer=None):
    g = StateGraph(ScanState)
    g.add_node("quality_gate", quality_gate)
    g.add_node("submit_reconstruction", submit_reconstruction)
    g.add_node("await_reconstruction", await_reconstruction)
    g.add_node("measure", measure)
    g.add_node("vision_read", vision_read)
    g.add_node("review", review)

    g.add_edge(START, "quality_gate")
    g.add_conditional_edges("quality_gate", route_after_quality,
                            {"submit_reconstruction": "submit_reconstruction", "__end__": END})
    g.add_edge("submit_reconstruction", "await_reconstruction")
    g.add_edge("await_reconstruction", "measure")
    g.add_edge("measure", "vision_read")
    g.add_edge("vision_read", "review")
    g.add_edge("review", END)

    return g.compile(checkpointer=checkpointer)


def make_checkpointer() -> SqliteSaver:
    """Persistent SQLite checkpointer for a long-lived server process."""
    conn = sqlite3.connect(get_settings().checkpoint_db, check_same_thread=False)
    return SqliteSaver(conn)
