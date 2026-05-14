from typing import Any

from loguru import logger

from .state import AgentState
from .tools import (
    analyze_sentiment,
    find_related,
    get_timeline,
    get_trending,
    search_news,
    summarize_article,
)


def planner_node(state: AgentState) -> AgentState:
    """Choose the most appropriate tool for a user query."""
    query = state.get("user_query", "")
    logger.info("planner_node received query=%s", query)
    if "ringkas" in query or "ringkasan" in query:
        state["selected_tool"] = "summarize_article"
        state["tool_inputs"] = {"url": state.get("tool_inputs", {}).get("url", "")}
    elif "timeline" in query or "perkembangan" in query:
        state["selected_tool"] = "get_timeline"
        state["tool_inputs"] = {"topic": query, "days": 7}
    elif "trending" in query or "terkini" in query:
        state["selected_tool"] = "get_trending"
        state["tool_inputs"] = {"category": "all", "hours": 24}
    elif "sentimen" in query or "positif" in query or "negatif" in query:
        state["selected_tool"] = "analyze_sentiment"
        state["tool_inputs"] = {"text": query}
    elif "terkait" in query or "related" in query:
        state["selected_tool"] = "find_related"
        state["tool_inputs"] = {"topic": query, "top_k": 3}
    else:
        state["selected_tool"] = "search_news"
        state["tool_inputs"] = {"query": query, "top_k": 5}
    state.setdefault("reasoning", []).append(f"Picked tool {state['selected_tool']} for query")
    return state


def tool_executor(state: AgentState) -> AgentState:
    """Execute the selected tool and attach the results to the state."""
    tool = state.get("selected_tool")
    inputs = state.get("tool_inputs", {})
    try:
        if tool == "search_news":
            output = search_news(**inputs)
        elif tool == "get_trending":
            output = get_trending(**inputs)
        elif tool == "analyze_sentiment":
            output = analyze_sentiment(**inputs)
        elif tool == "summarize_article":
            output = summarize_article(**inputs)
        elif tool == "find_related":
            output = find_related(**inputs)
        elif tool == "get_timeline":
            output = get_timeline(**inputs)
        else:
            output = {"error": "Tool tidak dikenali"}
        state["tool_output"] = output
        state.setdefault("reasoning", []).append(f"Executed {tool}")
    except Exception as exc:
        state["error"] = str(exc)
        logger.exception("tool_executor failed")
    return state


def analyzer_node(state: AgentState) -> AgentState:
    """Synthesize the tool output into an insight string."""
    output = state.get("tool_output")
    reasoning = state.setdefault("reasoning", [])
    if isinstance(output, list) and output:
        state["analysis"] = f"Menemukan {len(output)} hasil relevan."
    elif isinstance(output, dict) and output.get("label"):
        state["analysis"] = f"Sentimen terdeteksi: {output['label']} ({output['score']:.2f})."
    elif isinstance(output, str):
        state["analysis"] = output
    else:
        state["analysis"] = "Tidak ada hasil yang cukup jelas untuk dianalisis."
    reasoning.append("Synthesized tool output into analysis")
    return state


def responder_node(state: AgentState) -> AgentState:
    """Format final assistant response based on analysis and tool output."""
    reasoning = state.setdefault("reasoning", [])
    if state.get("error"):
        state["response"] = f"Maaf, terjadi kesalahan: {state['error']}"
    elif state.get("selected_tool") == "search_news":
        items = state.get("tool_output", [])
        lines = [f"{idx+1}. {item.get('title')} ({item.get('source')})" for idx, item in enumerate(items)]
        state["response"] = "Berikut berita yang relevan:\n" + "\n".join(lines)
    elif state.get("selected_tool") == "get_trending":
        top = state.get("tool_output", [])
        state["response"] = "Top trending saat ini:\n" + "\n".join([f"- {item['source']}: {item['latest_title']}" for item in top])
    elif state.get("selected_tool") == "analyze_sentiment":
        sentiment = state.get("tool_output", {})
        state["response"] = f"Sentimen: {sentiment.get('label')} ({sentiment.get('score'):.2f})."
    elif state.get("selected_tool") == "summarize_article":
        state["response"] = f"Ringkasan artikel:\n{state.get('tool_output')}"
    elif state.get("selected_tool") == "find_related":
        related = state.get("tool_output", [])
        state["response"] = "Artikel terkait:\n" + "\n".join([f"- {item.get('title')}" for item in related])
    elif state.get("selected_tool") == "get_timeline":
        timeline = state.get("tool_output", [])
        state["response"] = "Timeline topik:\n" + "\n".join([f"{row['date']}: {row['count']}" for row in timeline])
    else:
        state["response"] = state.get("analysis", "Saya tidak menemukan jawaban yang sesuai.")
    reasoning.append("Formatted final response")
    return state
