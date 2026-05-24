"""
LangGraph agent graph — Sora AI Timetable Assistant.

Graph:  START → agent → tools → agent (loop) → END
                              ↑ interrupt() from ask_user pauses here

Features:
  • MemorySaver checkpointer — enables interrupt/resume across HTTP requests
  • interrupt() in ask_user  — pauses mid-execution for human decisions
  • memory_context injection — compressed history + relevant past sessions
  • stream(stream_mode="updates") — each node emits events for SSE
"""
from __future__ import annotations

import os

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.agents.state import AdjustmentState
from app.agents.tools import ALL_TOOLS

_SYSTEM_BASE = """\
You are Sora, an expert AI assistant for the Shedulex academic timetabling system.
You help timetable officers make intelligent, conflict-free scheduling decisions.

=== TOOLS ===
• get_timetable_entries      — list all sessions with IDs (ALWAYS call first)
• detect_timetable_conflicts — find lecturer/room/group clashes
• get_available_rooms        — find rooms by capacity and type
• get_lecturer_free_slots    — find when a lecturer is free
• suggest_best_venue         — recommend the best-fit room
• move_timetable_entry       — move ONE session to a different time slot
• swap_timetable_entries     — swap the time slots of TWO sessions that are at DIFFERENT times
• get_available_lecturers    — list all active lecturers (for finding substitutes)
• substitute_lecturer        — replace a sick/absent lecturer across ALL their sessions in a timetable
• ask_user                   — PAUSE and ask the human for a decision

=== CONFLICT RESOLUTION RULES ===
A conflict means two sessions are scheduled at THE SAME time. The correct fix is:
  1. Call get_lecturer_free_slots (or review entries) to find a FREE time slot.
  2. Call move_timetable_entry to move ONE of the conflicting sessions to that free slot.
  3. NEVER call swap_timetable_entries on two sessions that share the same time — swapping
     them just exchanges their IDs with no visible change and wastes the user's time.
  4. swap_timetable_entries is ONLY useful when two sessions are at DIFFERENT times and
     you want to exchange their positions (e.g., swap Monday 9am ↔ Wednesday 2pm).

=== SICK LECTURER SUBSTITUTION ===
When a lecturer is sick, absent, or unavailable:
  1. Call get_timetable_entries to see the sick lecturer's sessions and get their lecturer_id.
  2. Call get_available_lecturers to find a qualified replacement (same department/specialization preferred).
  3. If multiple candidates exist, call ask_user to let the human choose.
  4. Call substitute_lecturer with the sick_lecturer_id, replacement_lecturer_id, and a clear reason.
  5. The tool replaces the lecturer on ALL their entries in the timetable at once.
  6. After substitution, check for new conflicts with detect_timetable_conflicts.

=== MOVE/SWAP RULES ===
1. ALWAYS call get_timetable_entries first to get real entry_id / time_slot_id values.
   Never invent UUIDs.
2. Before moving, call get_lecturer_free_slots or review entries to find a slot where
   the lecturer, room, and student group are all free.
3. Only claim success when a tool returns "Move successful:", "Swap successful:", or "Substitution successful:".
4. If a move would create a NEW conflict, call ask_user BEFORE proceeding.
   Describe the conflict clearly and offer labelled options (A / B / C …).
5. After the user responds via ask_user, implement their chosen option automatically.
6. If a tool returns "failed:", explain why and what the user can do next.
7. Always pass a reason= when calling move, swap, or substitute tools.
8. End every response with a brief plain-English summary of what was done or found.

=== SESSION ===
Operating for: {user_name}
Timetable ID:  {timetable_id}
"""


def _system_prompt(state: AdjustmentState) -> str:
    base = _SYSTEM_BASE.format(
        user_name=state.get("user_name") or "timetable officer",
        timetable_id=state.get("timetable_id") or "unknown",
    )
    mem = (state.get("memory_context") or "").strip()
    return base + ("\n\n" + mem if mem else "")


def _build_graph():
    model = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        temperature=0,
        streaming=True,
    ).bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    def agent_node(state: AdjustmentState) -> dict:
        messages = list(state["messages"])
        sys = SystemMessage(content=_system_prompt(state))
        # Always keep system message fresh (memory_context may differ per run)
        messages_no_sys = [m for m in messages if not isinstance(m, SystemMessage)]
        response = model.invoke([sys] + messages_no_sys)
        return {"messages": [response]}

    def route_after_agent(state: AdjustmentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AdjustmentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def thread_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}, "recursion_limit": 48}
