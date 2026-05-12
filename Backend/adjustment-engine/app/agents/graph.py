"""
LangGraph agent graph for intelligent timetable adjustment.

Graph topology:
  START → classify_intent → agent_node → tool_node → agent_node (loop) → END

The agent loops calling tools until it resolves the request or hits the
step limit, then summarises its actions.
"""
from __future__ import annotations
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from app.agents.state import AdjustmentState
from app.agents.tools import ALL_TOOLS

_SYSTEM_PROMPT = """You are an expert academic timetable scheduling assistant for the Shedulex system.
You help timetable officers and administrators intelligently manage and adjust academic schedules.

You have access to the following tools:
- get_timetable_entries: inspect a timetable (returns entry ids, courses, rooms, time_slot ids)
- detect_timetable_conflicts: find scheduling conflicts
- get_available_rooms: find available rooms by capacity/type
- get_lecturer_free_slots: find free slots for a lecturer
- move_timetable_entry: move ONE entry to a new time_slot_id when that slot is free for the same lecturer AND room
- swap_timetable_entries: exchange time slots between TWO entries (use when you need to swap two classes)
- suggest_best_venue: recommend the best room for a class size

Critical rules:
1. Never claim a schedule change succeeded unless the corresponding tool returned a message starting with "Move successful:" or "Swap successful:".
2. Prefer move_timetable_entry when moving to an empty slot; use swap_timetable_entries when exchanging two occupied slots.
3. Always call get_timetable_entries first to obtain real entry_id and time_slot_id values from the database — never invent UUIDs.
4. If a tool returns "failed:", explain the failure and what the user can do next — do not pretend it worked.

Be professional, concise, and academic in tone.
"""


def _build_graph():
    model = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        temperature=0,
    ).bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    def agent_node(state: AdjustmentState) -> dict:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=_SYSTEM_PROMPT)] + messages
        response = model.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AdjustmentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AdjustmentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# Module-level singleton — compiled once, reused across requests
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph
