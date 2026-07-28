"""Unit tests for the LangGraph agent pipeline in app.agents.graph."""

from __future__ import annotations

import pytest


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def mock_vector_store(monkeypatch):
    """Mock vector_store.search to return deterministic chunks."""

    async def _fake_search(*args, **kwargs):
        return [
            {
                "text": "Relevant legal text about contracts.",
                "score": 0.95,
                "chunk_id": "test-1",
                "document_id": "doc-1",
                "search_type": "semantic",
            }
        ]

    monkeypatch.setattr("app.agents.graph.vector_store.search", _fake_search)
    return _fake_search


@pytest.fixture
def mock_llm(monkeypatch):
    """Mock llm_complete to return a deterministic JSON response."""

    async def _fake_llm(*args, **kwargs):
        return (
            '{"document_type": "contract", "parties": ["Test Party"], '
            '"dates": [], "amounts": [], "summary": "Test summary"}'
        )

    # Patch at the original module
    monkeypatch.setattr("app.core.llm.llm_complete", _fake_llm)
    # Also patch at each import site so that local references pick up the mock
    monkeypatch.setattr("app.agents.graph.llm_complete", _fake_llm)
    monkeypatch.setattr("app.agents.analyzer.llm_complete", _fake_llm)
    monkeypatch.setattr("app.agents.drafter.llm_complete", _fake_llm)
    return _fake_llm


@pytest.fixture
def mock_llm_error(monkeypatch):
    """Mock llm_complete to raise an exception."""

    async def _fake_llm_error(*args, **kwargs):
        raise ValueError("LLM API error")

    monkeypatch.setattr("app.core.llm.llm_complete", _fake_llm_error)
    monkeypatch.setattr("app.agents.graph.llm_complete", _fake_llm_error)
    monkeypatch.setattr("app.agents.analyzer.llm_complete", _fake_llm_error)
    monkeypatch.setattr("app.agents.drafter.llm_complete", _fake_llm_error)
    return _fake_llm_error


# ── Tests for route_next ────────────────────────────────────────


class TestRouteNext:
    """Tests for the route_next router function."""

    @pytest.mark.asyncio
    async def test_route_next_increments(self):
        """Returns the step at the current step_index."""
        from app.agents.graph import route_next

        state: dict = {
            "steps": ["extract", "analyze", "draft"],
            "step_index": 0,
        }
        assert route_next(state) == "extract"

        state["step_index"] = 1
        assert route_next(state) == "analyze"

        state["step_index"] = 2
        assert route_next(state) == "draft"

    @pytest.mark.asyncio
    async def test_route_next_end(self):
        """When step_index >= len(steps), returns __end__."""
        from app.agents.graph import route_next

        state: dict = {
            "steps": ["extract", "analyze", "draft"],
            "step_index": 3,
        }
        assert route_next(state) == "__end__"

        state["steps"] = ["extract"]
        state["step_index"] = 1
        assert route_next(state) == "__end__"

        state["steps"] = ["draft"]
        state["step_index"] = 1
        assert route_next(state) == "__end__"

    @pytest.mark.asyncio
    async def test_route_next_default_steps(self):
        """When no steps key in state, defaults to ['draft']."""
        from app.agents.graph import route_next

        state: dict = {"step_index": 0}
        assert route_next(state) == "draft"

        state["step_index"] = 1
        assert route_next(state) == "__end__"

    @pytest.mark.asyncio
    async def test_route_next_empty_steps(self):
        """When steps is an empty list, returns __end__."""
        from app.agents.graph import route_next

        state: dict = {"steps": [], "step_index": 0}
        assert route_next(state) == "__end__"


# ── Tests for create_agent_graph ────────────────────────────────


class TestCreateAgentGraph:
    """Tests for graph construction."""

    @pytest.mark.asyncio
    async def test_create_graph_returns_compiled_graph(self):
        """create_agent_graph() returns a compiled StateGraph with invoke methods."""
        from app.agents.graph import create_agent_graph

        graph = create_agent_graph()
        assert graph is not None
        assert hasattr(graph, "ainvoke")
        assert hasattr(graph, "stream")
        assert hasattr(graph, "nodes")

    @pytest.mark.asyncio
    async def test_graph_has_expected_nodes(self):
        """The compiled graph contains all expected node names."""
        from app.agents.graph import create_agent_graph

        graph = create_agent_graph()
        expected_nodes = {
            "retrieve",
            "supervisor",
            "router",
            "extract",
            "analyze",
            "review",
            "draft",
            "send",
        }
        actual_nodes = set(graph.nodes.keys())
        assert expected_nodes.issubset(actual_nodes), (
            f"Missing nodes: {expected_nodes - actual_nodes}"
        )


# ── Tests for run_agent_pipeline ────────────────────────────────


class TestRunAgentPipeline:
    """Tests for the full agent pipeline execution."""

    @pytest.mark.asyncio
    async def test_pipeline_with_default_steps(
        self, mock_vector_store, mock_llm
    ):
        """Runs pipeline with no custom steps; supervisor auto-selects."""
        from app.agents.graph import run_agent_pipeline

        result = await run_agent_pipeline(
            document_id="test-doc-default",
            query="Analyze this contract",
            messages=[],
        )

        assert isinstance(result, dict)
        assert "analysis" in result
        assert "draft" in result
        assert "steps_executed" in result
        # With no custom steps, the supervisor should have selected steps
        assert len(result["steps_executed"]) > 0

    @pytest.mark.asyncio
    async def test_pipeline_with_custom_steps(
        self, mock_vector_store, mock_llm
    ):
        """Runs pipeline with a specific list of steps."""
        from app.agents.graph import run_agent_pipeline

        custom_steps = ["extract"]
        result = await run_agent_pipeline(
            document_id="test-doc-custom",
            query="Extract metadata",
            messages=[],
            steps=custom_steps,
        )

        assert isinstance(result, dict)
        assert "analysis" in result
        # Only "extract" was in steps, so draft should be empty
        assert result["draft"] == ""
        assert result["steps_executed"] == custom_steps

    @pytest.mark.asyncio
    async def test_pipeline_returns_expected_keys(
        self, mock_vector_store, mock_llm
    ):
        """Returns a dict with all expected keys from a successful run."""
        from app.agents.graph import run_agent_pipeline

        result = await run_agent_pipeline(
            document_id="test-doc-keys",
            query="Full pipeline test",
            messages=[],
            steps=["extract", "draft"],
        )

        expected_keys = {
            "analysis",
            "review",
            "draft",
            "document_type",
            "steps_executed",
            "processing_time_ms",
        }
        assert expected_keys.issubset(result.keys()), (
            f"Missing keys: {expected_keys - result.keys()}"
        )
        assert isinstance(result["analysis"], dict)
        assert result["review"] is None or isinstance(result["review"], str)
        assert isinstance(result["draft"], str)
        assert isinstance(result["document_type"], str)
        assert isinstance(result["steps_executed"], list)
        assert isinstance(result["processing_time_ms"], (int, float))

    @pytest.mark.asyncio
    async def test_pipeline_empty_document(
        self, mock_vector_store, mock_llm
    ):
        """Works with an empty document ID."""
        from app.agents.graph import run_agent_pipeline

        result = await run_agent_pipeline(
            document_id="",
            query="Test with empty doc ID",
            messages=[],
            steps=["extract", "draft"],
        )

        assert isinstance(result, dict)
        assert "analysis" in result
        assert "draft" in result
        # Should have completed without error
        assert "error" not in result or not result.get("error")

    @pytest.mark.asyncio
    async def test_pipeline_handles_llm_error(
        self, mock_vector_store, mock_llm_error
    ):
        """When llm_complete raises, pipeline returns an error dict gracefully."""
        from app.agents.graph import run_agent_pipeline

        result = await run_agent_pipeline(
            document_id="test-doc-error",
            query="Trigger LLM error",
            messages=[],
            steps=["draft"],
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] != ""
        # Even on error, the result should have the standard keys
        assert "analysis" in result
        assert "review" in result
        assert "draft" in result
        assert "steps_executed" in result
        assert "processing_time_ms" in result
