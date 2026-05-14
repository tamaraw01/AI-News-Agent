from datetime import datetime
from typing import Any

from pydantic import BaseModel, HttpUrl


class ArticleBase(BaseModel):
    title: str
    content: str | None = None
    source: str
    category: str
    published_at: str | None = None
    url: HttpUrl
    source_type: str


class ArticleCreate(ArticleBase):
    model_config = {}


class ArticleRead(ArticleBase):
    id: int
    url_hash: str
    embedding_status: bool
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class SearchResult(BaseModel):
    id: str
    title: str
    source: str
    published_at: str | None = None
    category: str | None = None
    score: float | None = None


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    reasoning: list[str]


class DigestRead(BaseModel):
    name: str
    summary: str
    payload: dict[str, Any] | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
