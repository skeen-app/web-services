from datetime import date
from enum import Enum
from typing import Protocol

from pydantic import BaseModel


class ArticleCategory(str, Enum):
    """Coarse buckets surfaced as filter chips on the mobile feed.

    Drives the PubMed query template the application service composes —
    keeping the categorisation in the domain (instead of as free text
    in the API layer) makes it trivial to add another bucket later.
    """

    ALL = "all"
    PREVENTION = "prevention"
    DETECTION = "detection"
    TREATMENT = "treatment"


class ArticleAuthor(BaseModel):
    """One author of a published article.

    ``country`` is best-effort — extracted from the affiliation string
    by the PubMed adapter and may be ``None`` when the affiliation is
    missing or doesn't end in a recognisable country fragment.
    """

    name: str
    country: str | None = None
    affiliation: str | None = None


class ArticleEntity(BaseModel):
    """One curated item shown on the Insights feed.

    ``url`` always points to the upstream canonical URL (PubMed for now),
    so the mobile app can hand it off to the platform browser without
    parsing anything PubMed-specific.
    """

    id: str
    title: str
    summary: str | None = None
    authors: list[ArticleAuthor] = []
    journal: str | None = None
    published_at: date | None = None
    article_type: str | None = None
    url: str
    category: ArticleCategory


class IExpertsRepository(Protocol):
    """Outbound port for the article catalogue.

    The application service depends on this protocol, not on PubMed.
    Swapping for another upstream (Europe PMC, GNews, etc.) is a single-
    file infrastructure change.
    """

    async def search(
        self,
        query: str,
        category: ArticleCategory,
        limit: int,
    ) -> list[ArticleEntity]:
        ...
