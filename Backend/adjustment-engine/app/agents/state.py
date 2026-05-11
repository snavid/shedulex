"""
LangGraph state definition for the timetable adjustment agent.
State flows through graph nodes and accumulates tool call results.
"""
from __future__ import annotations
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class AdjustmentState(TypedDict):
    messages: Annotated[list, add_messages]
    timetable_id: str
    intent: str             # move_class | find_free_slot | resolve_conflicts | suggest_venue
    resolved: bool
    suggestions: list[dict]
    conflicts: list[dict]
    context: dict           # cached timetable data
