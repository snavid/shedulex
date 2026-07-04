import sys
import types
from unittest.mock import MagicMock


def _ensure_module(name: str) -> types.ModuleType:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
    return sys.modules[name]


# Stub heavy AI deps so tests can run without langchain/langgraph installed locally.
for _mod in (
    "langchain_core",
    "langchain_core.messages",
    "langgraph",
    "langgraph.types",
    "langgraph.graph",
    "langgraph.graph.message",
    "langgraph.prebuilt",
    "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
    "langchain_openai",
    "chromadb",
    "chromadb_client",
):
    _ensure_module(_mod)

sys.modules["langchain_core.messages"].HumanMessage = MagicMock
sys.modules["langchain_core.messages"].ToolMessage = MagicMock
sys.modules["langchain_core.messages"].SystemMessage = MagicMock
sys.modules["langgraph.types"].Command = MagicMock
sys.modules["langgraph.graph"].START = MagicMock()
sys.modules["langgraph.graph"].END = MagicMock()
sys.modules["langgraph.graph"].StateGraph = MagicMock
sys.modules["langgraph.graph.message"].add_messages = MagicMock()
sys.modules["langgraph.prebuilt"].ToolNode = MagicMock
sys.modules["langgraph.checkpoint.memory"].MemorySaver = MagicMock

# Stub agent submodules so route import does not load LangGraph/OpenAI.
_graph_mod = _ensure_module("app.agents.graph")
_graph_mod.get_graph = MagicMock(return_value=MagicMock())
_graph_mod.thread_config = MagicMock(return_value={"configurable": {"thread_id": "test"}, "recursion_limit": 48})
_state_mod = _ensure_module("app.agents.state")
_state_mod.AdjustmentState = dict
_tools_mod = _ensure_module("app.agents.tools")
_memory_mod = _ensure_module("app.services.memory")
_memory_mod.compress_session = MagicMock(return_value=False)
_memory_mod.build_memory_context = MagicMock(return_value="")
_vector_mod = _ensure_module("app.services.vector_store")
_vector_mod.store_session_summary = MagicMock()
_vector_mod.retrieve_relevant_context = MagicMock(return_value="")

import pytest
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    yield _db
    _db.session.rollback()
