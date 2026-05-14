from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from core.database import Base


class Article(Base):
    """News article model with full global metadata."""

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    hash = Column(String(64), unique=True, nullable=False, index=True)
    url = Column(String(1024), unique=True, nullable=False)
    title = Column(String(512), nullable=False)
    original_title = Column(String(512), nullable=True)  # Before translation
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)  # AI-generated summary
    source = Column(String(256), nullable=False, index=True)
    source_type = Column(String(64), nullable=False)  # rss, api, reddit, etc
    category = Column(String(128), nullable=False, index=True)
    language = Column(String(10), default="en", index=True)  # ISO 639-1
    original_language = Column(String(10), nullable=True)  # Before translation
    country = Column(String(2), nullable=True, index=True)  # ISO 3166-1 alpha-2
    url_image = Column(String(1024), nullable=True)
    
    # Sentiment & Analysis
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_label = Column(String(20), nullable=True)  # positive, negative, neutral
    entities = Column(JSON, nullable=True)  # List of extracted entities
    keywords = Column(JSON, nullable=True)  # Top 5 keywords
    
    # Metadata
    embedding_id = Column(String(64), nullable=True)  # ChromaDB ID
    is_breaking = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    published_at = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    entity_mentions = relationship("EntityMention", back_populates="article", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_article_hash", "hash"),
        Index("idx_article_source", "source"),
        Index("idx_article_published", "published_at"),
        Index("idx_article_country", "country"),
    )


class Topic(Base):
    """Trending topic/cluster."""

    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), unique=True, nullable=False, index=True)
    slug = Column(String(256), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    article_count = Column(Integer, default=0)
    trend_velocity = Column(Float, default=0.0)  # Change rate
    last_seen_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_trending = Column(Boolean, default=False, index=True)
    is_breaking = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alert(Base):
    """Breaking news alert."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=True)
    keyword = Column(String(256), nullable=False)
    category = Column(String(128), nullable=True)
    min_articles = Column(Integer, default=3)
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DigestLog(Base):
    """Log of sent digests."""

    __tablename__ = "digest_logs"

    id = Column(Integer, primary_key=True, index=True)
    digest_type = Column(String(50), nullable=False)  # daily, weekly, on-demand
    user_count = Column(Integer, default=0)
    article_count = Column(Integer, default=0)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)
    metadata_json = Column("metadata", JSON, nullable=True)


class UserSession(Base):
    """User session and preferences."""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(128), nullable=True)
    language_pref = Column(String(10), default="id")  # id, en, etc
    categories_pref = Column(JSON, nullable=True)  # Custom category selection
    countries_pref = Column(JSON, nullable=True)  # Custom country filter
    digest_hour = Column(Integer, default=7)
    digest_enabled = Column(Boolean, default=True)
    breaking_alerts_enabled = Column(Boolean, default=True)
    alert_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EntityMention(Base):
    """Extracted entity mentions from articles."""

    __tablename__ = "entity_mentions"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    entity_text = Column(String(256), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # PERSON, ORG, GPE, EVENT, etc
    frequency = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    article = relationship("Article", back_populates="entity_mentions")


class SourceStats(Base):
    """Statistics per news source."""

    __tablename__ = "source_stats"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(256), unique=True, nullable=False)
    article_count = Column(Integer, default=0)
    last_article_at = Column(DateTime, nullable=True)
    avg_fetch_time = Column(Float, default=0.0)  # seconds
    success_rate = Column(Float, default=1.0)  # 0-1
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
