from __future__ import annotations
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class AdjustmentState(TypedDict):
    messages:           Annotated[list, add_messages]
    timetable_id:       str
    session_id:         str
    user_name:          str
    # Compressed history + relevant past sessions, injected into system prompt
    memory_context:     str
    # Human-in-the-loop state
    waiting_for_input:  bool
    interrupt_question: str
    # Informational fields
    intent:             str
    resolved:           bool
    suggestions:        list[dict]
    conflicts:          list[dict]
    context:            dict
