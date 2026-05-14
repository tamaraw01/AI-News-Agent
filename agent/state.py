from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Schema untuk state agent pada StateGraph."""

    user_query: str
    selected_tool: str
    tool_inputs: dict[str, Any]
    tool_output: Any
    analysis: str
    response: str
    reasoning: list[str]
    error: str
