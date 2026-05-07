"""Use-case service for the Insights feed.

Wraps the upstream repository with an in-process TTL cache so a screen
that polls every time the user toggles a filter chip doesn't burn the
PubMed quota. Six-hour TTL is a sensible default — clinical literature
moves on a weekly-or-slower cadence, so a cached page that's a few hours
stale is indistinguishable from a fresh one to the reader.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.core.logger import get_logger
from src.features.experts.api.schemas import (
    ArticleAuthorResponse,
    ArticleResponse,
    ArticlesListResponse,
)
from src.features.experts.domain.entities import (
    ArticleCategory,
    ArticleEntity,
    IExpertsRepository,
)

logger = get_logger(__name__)


@dataclass
class _CacheEntry:
    items: list[ArticleEntity]
    expires_at: float


class _TTLCache:
    """Tiny in-process TTL cache. We don't pull in ``cachetools`` for
    one use-site — keys collide rarely (query × category × limit) and
    eviction is lazy on read.
    """

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> list[ArticleEntity] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            del self._store[key]
            return None
        return entry.items

    def set(self, key: str, items: list[ArticleEntity]) -> None:
        self._store[key] = _CacheEntry(
            items=items, expires_at=time.monotonic() + self._ttl
        )


class ExpertsService:
    CACHE_TTL_S = 6 * 60 * 60

    def __init__(self, repository: IExpertsRepository):
        self._repo = repository
        self._cache = _TTLCache(ttl_seconds=self.CACHE_TTL_S)

    async def list_articles(
        self,
        query: str | None,
        category: ArticleCategory,
        limit: int,
    ) -> ArticlesListResponse:
        normalised_query = (query or "").strip().lower()
        cache_key = f"{category.value}::{limit}::{normalised_query}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(
                "ExpertsService: cache hit (%s, q='%s')",
                category.value, normalised_query,
            )
            return self._to_response(
                items=cached,
                category=category,
                query=normalised_query or None,
                cached=True,
            )

        items = await self._repo.search(
            query=normalised_query,
            category=category,
            limit=limit,
        )
        # Only cache non-empty responses — when the upstream blips and
        # returns nothing we want the next request to retry, not serve
        # an empty page for six hours.
        if items:
            self._cache.set(cache_key, items)

        logger.info(
            "ExpertsService: fetched %d articles (%s, q='%s')",
            len(items), category.value, normalised_query,
        )
        return self._to_response(
            items=items,
            category=category,
            query=normalised_query or None,
            cached=False,
        )

    @staticmethod
    def _to_response(
        items: list[ArticleEntity],
        category: ArticleCategory,
        query: str | None,
        cached: bool,
    ) -> ArticlesListResponse:
        return ArticlesListResponse(
            items=[
                ArticleResponse(
                    id=a.id,
                    title=a.title,
                    summary=a.summary,
                    authors=[
                        ArticleAuthorResponse(
                            name=author.name,
                            country=author.country,
                            affiliation=author.affiliation,
                        )
                        for author in a.authors
                    ],
                    journal=a.journal,
                    published_at=a.published_at,
                    article_type=a.article_type,
                    url=a.url,
                    category=a.category,
                )
                for a in items
            ],
            total=len(items),
            category=category,
            query=query,
            cached=cached,
        )
