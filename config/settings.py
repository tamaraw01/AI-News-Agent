from functools import lru_cache
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── LLM & API Keys (Required) ───
    groq_api_key: str = ""
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    google_api_key: str = Field(default="", validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"))
    telegram_bot_token: str = ""
    telegram_admin_id: int = 0
    telegram_channel_id: str = ""
    telegram_chat_id: str = ""

    # ─── News API Keys (Optional but recommended) ───
    newsapi_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ai-news-bot/1.0"
    mediastack_api_key: str = ""
    currents_api_key: str = ""
    gnews_api_key: str = ""

    # ─── Storage & Paths ───
    sqlite_path: Path = DATA_DIR / "news.db"
    chroma_persist_dir: Path = DATA_DIR / "chroma"
    chroma_path: Path = Field(default=DATA_DIR / "chroma", validation_alias=AliasChoices("CHROMA_PATH", "CHROMA_PERSIST_DIR"))
    database_url: str = ""
    logs_dir: Path = BASE_DIR / "logs"

    # ─── Ingestion Settings ───
    poll_interval_minutes: int = Field(
        default=15,
        validation_alias=AliasChoices("POLL_INTERVAL_MINUTES", "NEWS_UPDATE_INTERVAL_MINUTES"),
    )
    alert_check_interval_minutes: int = 5
    breaking_news_velocity_threshold: float = 10.0
    article_retention_days: int = 30
    max_articles_per_cycle: int = 500
    max_articles_per_source: int = Field(
        default=25,
        validation_alias=AliasChoices("MAX_ARTICLES_PER_SOURCE", "ARTICLES_PER_SOURCE"),
    )
    translation_enabled: bool = False

    # ─── Global Coverage ───
    enabled_countries: list[str] = Field(
        default=["us", "gb", "id", "in", "au", "ca", "de", "fr", "jp", "br", "za", "ng", "mx", "eg"],
    )
    enabled_languages: list[str] = Field(
        default=["en", "id", "de", "fr", "ja", "pt", "ar", "es"],
    )

    # ─── News API Endpoints ───
    newsapi_endpoint: HttpUrl = Field(default="https://newsapi.org/v2/top-headlines")
    gdelt_rss_url: HttpUrl = Field(default="https://news.google.com/rss")
    gdelt_events_api: HttpUrl = Field(default="https://api.gdeltproject.org/api/v2/doc/doc")

    # ─── Telegram Schedule (WIB = UTC+7) ───
    daily_digest_hour: int = 7
    daily_digest_minute: int = 0
    weekly_digest_day: int = 0  # 0=Monday

    # ─── Categories & Models ───
    default_categories: list[str] = Field(
        default=[
            "technology", "business", "politics", "science",
            "health", "sports", "entertainment", "environment",
            "crime", "military", "economy", "social",
            "education", "disaster"
        ],
    )
    chroma_collection_name: str = Field(default="news_articles")
    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    spacy_model: str = Field(default="en_core_web_sm")
    llm_max_retries: int = 3
    llm_retry_delay: float = 2.0
    max_tokens_summary: int = 300
    max_tokens_answer: int = 500
    temperature: float = 0.3

    # ─── Application Settings ───
    app_name: str = Field(default="AI News Agent Pro")
    app_env: str = Field(default="production", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"))
    log_level: str = "INFO"
    debug: bool = False
    user_agent: str = Field(default="AI News Agent Pro/1.0 (+https://example.com)")

    def __init__(self, **data):
        super().__init__(**data)
        if self.google_api_key and not self.gemini_api_key:
            self.gemini_api_key = self.google_api_key
        if self.chroma_path and self.chroma_persist_dir == DATA_DIR / "chroma":
            self.chroma_persist_dir = self.chroma_path
        if self.database_url.startswith("sqlite:///"):
            self.database_url = self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if not self.database_url:
            self.database_url = f"sqlite+aiosqlite:///{self.sqlite_path}"
        # Ensure directories exist
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "development", "dev", "true", "1", "yes", "on"}:
                return True
        return value

    @field_validator("enabled_countries", "enabled_languages", "default_categories", mode="before")
    @classmethod
    def _parse_csv_list(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def enabled_countries_str(self) -> str:
        """Return comma-separated list of enabled countries for config display."""
        return ",".join(self.enabled_countries)

    @property
    def enabled_languages_str(self) -> str:
        """Return comma-separated list of enabled languages for config display."""
        return ",".join(self.enabled_languages)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached singleton settings instance."""
    return Settings()


settings = get_settings()
