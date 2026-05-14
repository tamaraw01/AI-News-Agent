from typing import Any

from .nodes import analyzer_node, planner_node, responder_node, tool_executor
from .state import AgentState


class FallbackStateGraph:
    """Fallback StateGraph implementation when LangGraph is not installed."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.nodes = [planner_node, tool_executor, analyzer_node, responder_node]

    def execute(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        state = initial_state.get("agent_state", {})
        for node in self.nodes:
            state = node(state)
        return {"agent_state": state}


try:
    from langgraph import StateGraph

    def create_agent_graph() -> StateGraph:
        """Create a LangGraph StateGraph for the AI News Agent."""
        graph = StateGraph(name="ai_news_agent")
        graph.add_state("agent_state", AgentState)
        graph.add_node("planner", planner_node, inputs=["agent_state"], outputs=["agent_state"])
        graph.add_node("executor", tool_executor, inputs=["agent_state"], outputs=["agent_state"])
        graph.add_node("analyzer", analyzer_node, inputs=["agent_state"], outputs=["agent_state"])
        graph.add_node("responder", responder_node, inputs=["agent_state"], outputs=["agent_state"])
        graph.connect("planner", "executor")
        graph.connect("executor", "analyzer")
        graph.connect("analyzer", "responder")
        return graph
except ImportError:  # pragma: no cover
    def create_agent_graph() -> FallbackStateGraph:
        """Create a fallback state graph implementation."""
        return FallbackStateGraph(name="ai_news_agent")
