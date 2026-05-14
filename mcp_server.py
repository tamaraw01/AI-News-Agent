"""FastMCP backend tools for AI News Agent.

Run locally:
    python mcp_server.py

Environment:
    MCP_HOST=0.0.0.0
    MCP_PORT=8001
    MCP_TRANSPORT=sse  # sse, http, or stdio
"""

from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from sqlalchemy import select

from agents.supervisor import handle_message
from analysis.sentiment import get_sentiment_distribution
from analysis.trending import get_trending_topics
from bot.formatters import format_daily_digest
from core.database import get_async_session, init_db
from core.models import Article
from notifications.scheduler_jobs import (
    _article_to_digest_dict,
    _local_daily_briefing,
    _select_diverse_articles,
)

mcp = FastMCP(
    name="AI News Agent Backend",
    instructions=(
        "Backend tools for news intelligence, local article search, daily digest "
        "preview, lightweight web/news search, and system diagnostics."
    ),
)


@mcp.tool
def news_search(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search local indexed news and return an intelligence-style briefing."""
    top_k = max(1, min(top_k, 10))
    result = handle_message(query, top_k=top_k)
    return {
        "query": query,
        "intent": result["intent"],
        "article_count": len(result["articles"]),
        "briefing_html": result["message"],
        "articles": result["articles"],
    }


@mcp.tool
async def daily_digest_preview(hours: int = 24, limit: int = 80) -> dict[str, Any]:
    """Build a daily digest preview from locally stored articles without sending Telegram messages."""
    await init_db()
    since = datetime.utcnow() - timedelta(hours=max(1, min(hours, 168)))
    async with get_async_session() as session:
        result = await session.execute(
            select(Article)
            .where(Article.published_at >= since)
            .order_by(Article.published_at.desc())
            .limit(max(10, min(limit, 200)))
        )
        articles = result.scalars().all()

    trending = await get_trending_topics(hours=hours, limit=10)
    selected = _select_diverse_articles(articles, limit=10)
    sentiment = get_sentiment_distribution(articles)
    briefing = (
        _local_daily_briefing(selected, sentiment, trending)
        if articles
        else "Belum ada artikel baru dalam periode ini."
    )
    messages = format_daily_digest(
        {
            "total_articles": len(articles),
            "sources": len({article.source for article in articles}),
            "trending_count": len(trending),
            "sentiment_dist": sentiment,
            "briefing": briefing,
            "articles": [_article_to_digest_dict(article) for article in selected[:6]],
        }
    )
    return {
        "hours": hours,
        "total_articles": len(articles),
        "sources": len({article.source for article in articles}),
        "sentiment": sentiment,
        "messages": messages,
    }


@mcp.tool
def web_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Run a lightweight web search using DuckDuckGo HTML, with Google News RSS fallback."""
    limit = max(1, min(limit, 10))
    results: list[dict[str, str]] = []
    headers = {"User-Agent": "AI News Agent MCP/1.0"}

    try:
        response = httpx.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=12,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for node in soup.select(".result")[:limit]:
            title_node = node.select_one(".result__title a")
            snippet_node = node.select_one(".result__snippet")
            if not title_node:
                continue
            results.append(
                {
                    "title": title_node.get_text(" ", strip=True),
                    "url": title_node.get("href", ""),
                    "snippet": snippet_node.get_text(" ", strip=True) if snippet_node else "",
                }
            )
    except Exception:
        results = []

    if not results:
        feed_url = f"https://news.google.com/rss/search?q={quote_plus(query)}"
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            results.append(
                {
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "snippet": entry.get("summary", ""),
                }
            )

    return {"query": query, "count": len(results), "results": results}


@mcp.tool
def system_info() -> dict[str, Any]:
    """Return runtime and host diagnostics for the backend."""
    return {
        "time_utc": datetime.utcnow().isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "uptime_hint": time.time(),
    }


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "sse").lower()
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8001"))

    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=transport, host=host, port=port)
