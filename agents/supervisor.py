from typing import Any

from agents import hunter, writer


def detect_intent(text: str) -> str:
    """Detect supported user intent."""
    return "search"


def handle_message(text: str, top_k: int = 5) -> dict[str, Any]:
    """Route user text through the agent workflow."""
    intent = detect_intent(text)
    if intent == "search":
        articles = hunter.search(text, top_k=top_k)
        return {"intent": intent, "articles": articles, "message": writer.format_results(text, articles)}
    return {"intent": intent, "articles": [], "message": "Maaf, intent belum didukung."}
