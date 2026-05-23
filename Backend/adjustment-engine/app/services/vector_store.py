"""
ChromaDB vector store for semantic session memory retrieval.

Stores compressed session summaries as embeddings.
At the start of each new session, queries the 3 most relevant past sessions
to inject as context, helping the agent recall past decisions.

Uses chromadb-client (HTTP client) connecting to the Chroma server container.
Falls back gracefully when Chroma is unavailable (not a hard dependency).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client = None
_collection = None
COLLECTION_NAME = "session_memory"


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        host = os.environ.get("CHROMA_HOST", "chromadb")
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        _client = chromadb.HttpClient(host=host, port=port)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB connected at %s:%s", host, port)
        return _collection
    except Exception as exc:
        logger.warning("ChromaDB unavailable (%s) — semantic memory disabled.", exc)
        return None


def store_session_summary(session_id: str, timetable_id: str, summary: str) -> None:
    """Upsert a session summary into ChromaDB for future retrieval."""
    if not summary.strip():
        return
    col = _get_collection()
    if col is None:
        return
    try:
        col.upsert(
            ids=[session_id],
            documents=[summary],
            metadatas=[{"timetable_id": timetable_id, "session_id": session_id}],
        )
    except Exception as exc:
        logger.warning("ChromaDB upsert failed: %s", exc)


def retrieve_relevant_context(timetable_id: str, query: str, top_k: int = 3) -> str:
    """
    Query ChromaDB for the most semantically similar past session summaries
    for the same timetable. Returns a formatted context string.
    """
    col = _get_collection()
    if col is None:
        return ""
    try:
        results = col.query(
            query_texts=[query],
            n_results=top_k,
            where={"timetable_id": timetable_id},
        )
        docs: list[str] = results.get("documents", [[]])[0]
        if not docs:
            return ""
        joined = "\n---\n".join(d for d in docs if d)
        return (
            "=== RELEVANT PAST SESSIONS ===\n"
            f"{joined}\n"
            "=== END PAST SESSIONS ===\n\n"
        )
    except Exception as exc:
        logger.warning("ChromaDB query failed: %s", exc)
        return ""
