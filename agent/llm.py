from loguru import logger

from config import settings


def create_main_llm() -> object | None:
    """Create the primary Groq LLM client if available."""
    try:
        from langchain_groq import ChatGroq
    except ImportError:
        logger.warning("Groq LLM package not available")
        return None

    try:
        return ChatGroq(
            groq_api_key=settings.groq_api_key,
            model="llama-3.3-70b-versatile",
            temperature=settings.temperature,
            max_tokens=settings.max_tokens_answer,
        )
    except Exception as exc:
        logger.exception("Failed to initialize Groq LLM: %s", exc)
        return None


def create_backup_llm() -> object | None:
    """Create the backup Google Gemini LLM client if available."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        logger.warning("Google Gemini package not available")
        return None

    try:
        return ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model="gemini-1.5-flash",
            temperature=settings.temperature,
            max_output_tokens=settings.max_tokens_answer,
        )
    except Exception as exc:
        logger.exception("Failed to initialize Google Gemini LLM: %s", exc)
        return None


def generate_text(prompt: str, max_tokens: int = 256) -> str:
    """Generate text using the primary LLM with fallback to backup."""
    llm = create_main_llm() or create_backup_llm()
    if llm is None:
        logger.warning("No LLM available, falling back to local summarization")
        return prompt

    try:
        if hasattr(llm, "invoke"):
            response = llm.invoke(prompt)
            return str(getattr(response, "content", response)).strip()
        if hasattr(llm, "generate"):
            response = llm.generate([prompt])
            return str(response.generations[0][0].text).strip()
        if hasattr(llm, "predict"):
            return llm.predict(prompt).strip()
        if hasattr(llm, "call"):
            return llm.call(prompt).strip()
    except Exception as exc:
        logger.exception("LLM request failed: %s", exc)

    return prompt
