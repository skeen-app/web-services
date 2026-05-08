from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.logger import get_logger
from src.features.experts.api.schemas import ArticlesListResponse
from src.features.experts.application.services import ExpertsService
from src.features.experts.domain.entities import ArticleCategory
from src.features.experts.infrastructure.pubmed_adapter import PubmedAdapter

logger = get_logger(__name__)
router = APIRouter()


# Module-level singleton — the in-process TTL cache has to outlive the
# request so a second call within the TTL window can short-circuit
# upstream. A FastAPI ``Depends`` factory would re-instantiate per-call
# and defeat the cache.
_service: ExpertsService | None = None


def get_experts_service() -> ExpertsService:
    global _service
    if _service is None:
        _service = ExpertsService(repository=PubmedAdapter())
    return _service


@router.get("/articles", response_model=ArticlesListResponse)
async def list_articles(
    query: str | None = Query(default=None, max_length=120),
    category: ArticleCategory = Query(default=ArticleCategory.ALL),
    limit: int = Query(default=10, ge=1, le=20),
    service: ExpertsService = Depends(get_experts_service),
):
    """Returns curated dermatology articles from PubMed.

    Public endpoint — the content is read-only and not user-specific, so
    requiring auth would only add friction. Rate-limiting still applies
    via the global slowapi middleware if a per-route policy is added.
    """
    try:
        return await service.list_articles(
            query=query, category=category, limit=limit
        )
    except Exception as exc:
        logger.error(f"GET /experts/articles failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load articles right now.",
        )
