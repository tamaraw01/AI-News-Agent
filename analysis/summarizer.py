"""Multi-document article summarization."""

from typing import Optional

from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.prompts import SUMMARIZE_ARTICLES_PROMPT
from config.settings import settings
from core.models import Article


def get_groq_client():
    """Get Groq client."""
    from groq import Groq

    return Groq(api_key=settings.groq_api_key)


@retry(
    stop=stop_after_attempt(settings.llm_max_retries),
    wait=wait_exponential(min=settings.llm_retry_delay, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_groq(system_prompt: str, user_prompt: str) -> str:
    client = get_groq_client()
    message = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=settings.max_tokens_summary,
        temperature=settings.temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return message.choices[0].message.content or ""


async def multi_doc_summarize(
    articles: list[Article], query: Optional[str] = None, style: str = "brief"
) -> str:
    """Generate multi-document summary using Groq.

    Args:
        articles: List of articles to summarize
        query: Optional query to focus summary
        style: Summary style - "brief", "detail", or "report"

    Returns:
        Summary text
    """
    if not articles:
        return "No articles to summarize."

    if not settings.groq_api_key:
        logger.warning("Groq API key not configured")
        return "API not configured."

    try:
        # Limit articles for summarization
        summaries = articles[:10]

        # Build article text for LLM
        article_texts = []
        for i, article in enumerate(summaries, 1):
            text = f"Article {i} ({article.source}):\nTitle: {article.title}\n"
            if article.summary:
                text += f"Summary: {article.summary}\n"
            article_texts.append(text)

        combined_text = "\n".join(article_texts)

        # Build prompt
        system_prompt = SUMMARIZE_ARTICLES_PROMPT
        user_prompt = f"""
{combined_text}

Style: {style}
{f"Focus query: {query}" if query else ""}

Please provide a comprehensive summary of these articles."""

        summary = _call_groq(system_prompt, user_prompt)
        logger.info(f"Generated summary for {len(summaries)} articles")
        return summary

    except Exception as e:
        logger.error(f"Summarization error: {e}")
        return "Error generating summary."
