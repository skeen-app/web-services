from datetime import date

from pydantic import BaseModel, Field

from src.features.experts.domain.entities import ArticleCategory


class ArticleAuthorResponse(BaseModel):
    name: str
    country: str | None = None
    affiliation: str | None = None


class ArticleResponse(BaseModel):
    id: str
    title: str
    summary: str | None = None
    authors: list[ArticleAuthorResponse] = []
    journal: str | None = None
    published_at: date | None = None
    article_type: str | None = None
    url: str
    category: ArticleCategory


class ArticlesListResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    category: ArticleCategory
    query: str | None = None
    cached: bool = Field(
        default=False,
        description="True when the response was served from the in-process TTL cache.",
    )


__all__ = [
    "ArticleAuthorResponse",
    "ArticleResponse",
    "ArticlesListResponse",
]
