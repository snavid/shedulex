"""
Conversation memory management with LLM-based compression.

Strategy:
  - Keep the last 20 messages verbatim (recent context).
  - When total_messages >= SESSION_COMPRESS_THRESHOLD:
      summarise the older messages into compressed_summary using GPT-4o-mini.
  - When compressed_summary length >= SUMMARY_MAX_CHARS the session is "full"
    and the UI should prompt the user to start a new chat.
"""
from __future__ import annotations

import logging
import os

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# How many recent messages to keep verbatim (never compressed)
RECENT_WINDOW = 20


def _llm():
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        temperature=0,
    )


def compress_session(session) -> bool:
    """
    Summarise the older portion of session.messages into session.compressed_summary.
    Keeps the most recent RECENT_WINDOW messages untouched.
    Returns True if compression happened, False if not needed / no API key.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return False

    messages = session.messages or []
    if len(messages) <= RECENT_WINDOW:
        return False

    to_compress = messages[:-RECENT_WINDOW]
    keep_recent = messages[-RECENT_WINDOW:]

    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m.get('content', '')}"
        for m in to_compress
    )

    existing = session.compressed_summary or ""
    prior = f"Prior summary:\n{existing}\n\n" if existing else ""

    prompt = (
        f"{prior}Summarise the following timetable-adjustment conversation in ≤ 300 words. "
        "Preserve: decisions made, changes applied (what moved where), conflicts found, "
        "user preferences, and any unresolved issues. Be factual and concise.\n\n"
        f"{conversation_text}"
    )

    try:
        model = _llm()
        resp = model.invoke([HumanMessage(content=prompt)])
        session.compressed_summary = resp.content
        session.messages = keep_recent
        logger.info("Compressed session %s (%d → %d messages)", session.id, len(messages), len(keep_recent))
        return True
    except Exception as exc:
        logger.warning("Memory compression failed for session %s: %s", session.id, exc)
        return False


def build_memory_context(session) -> str:
    """Return the compressed summary as an injectable context string."""
    summary = (session.compressed_summary or "").strip()
    if not summary:
        return ""
    return (
        "=== CONVERSATION HISTORY (compressed) ===\n"
        f"{summary}\n"
        "=== END HISTORY ===\n\n"
        "The above summarises earlier messages in this session. Continue from there."
    )


def estimate_chars(session) -> int:
    total = len(session.compressed_summary or "")
    for m in (session.messages or []):
        total += len(str(m.get("content", "")))
    return total
