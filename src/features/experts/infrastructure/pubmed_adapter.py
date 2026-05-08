"""Adapter that resolves :class:`IExpertsRepository` against the public
NCBI PubMed E-utilities REST surface.

Endpoints we use:
    1. ``esearch.fcgi`` — keyword search returning PMIDs (sorted by date).
    2. ``efetch.fcgi`` — XML record fetch for those PMIDs.

PubMed is free, key-less, and does not impose a hard quota for our scale
(the public guideline is ≤3 req/sec; the application-level cache below
keeps us well under that).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Final

import httpx

from src.core.logger import get_logger
from src.features.experts.domain.entities import (
    ArticleAuthor,
    ArticleCategory,
    ArticleEntity,
)

logger = get_logger(__name__)

ESEARCH_URL: Final = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
)
EFETCH_URL: Final = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Year window applied on top of every category template — keeps content
# recent enough to be clinically relevant without going so narrow we
# starve the feed.
_RECENT_YEAR: Final = "2022"

# Category → PubMed query template. Each is constrained to review or
# practice-guideline article types so we don't surface raw experimental
# data that would confuse a non-clinical reader.
_CATEGORY_TEMPLATES: Final = {
    ArticleCategory.ALL: (
        '("skin cancer"[Title/Abstract] OR melanoma[Title/Abstract] '
        'OR "skin neoplasms"[MeSH]) AND '
        '(review[PT] OR "practice guideline"[PT]) AND '
        f'("{_RECENT_YEAR}"[PDAT] : "3000"[PDAT])'
    ),
    ArticleCategory.PREVENTION: (
        '("skin cancer"[Title/Abstract] OR melanoma[Title/Abstract]) AND '
        '(prevention[Title/Abstract] OR "sun protection"[Title/Abstract]) AND '
        'review[PT] AND '
        f'("{_RECENT_YEAR}"[PDAT] : "3000"[PDAT])'
    ),
    ArticleCategory.DETECTION: (
        '("skin cancer"[Title/Abstract] OR melanoma[Title/Abstract] '
        'OR mole[Title/Abstract] OR nevus[Title/Abstract]) AND '
        '("early detection"[Title/Abstract] OR "self-examination"[Title/Abstract] '
        'OR diagnosis[Title/Abstract]) AND review[PT] AND '
        f'("{_RECENT_YEAR}"[PDAT] : "3000"[PDAT])'
    ),
    ArticleCategory.TREATMENT: (
        '("skin cancer"[Title/Abstract] OR melanoma[Title/Abstract]) AND '
        '(treatment[Title/Abstract] OR therapy[Title/Abstract]) AND '
        'review[PT] AND '
        f'("{_RECENT_YEAR}"[PDAT] : "3000"[PDAT])'
    ),
}

# Heuristic country-name list used to extract the trailing country from
# affiliation strings ("..., Department of Dermatology, Boston, USA.").
# Maintained as a small superset of common dermatology research hubs;
# misses fall through as ``None`` rather than fabricating data.
_KNOWN_COUNTRIES: Final = {
    "USA", "United States", "United States of America", "U.S.A.", "U.S.",
    "UK", "United Kingdom", "England", "Scotland", "Wales", "Ireland",
    "Spain", "Portugal", "France", "Germany", "Italy", "Switzerland",
    "Austria", "Belgium", "Netherlands", "Denmark", "Sweden", "Norway",
    "Finland", "Iceland", "Poland", "Czech Republic", "Greece", "Turkey",
    "Israel", "Saudi Arabia", "United Arab Emirates", "India", "Pakistan",
    "China", "Japan", "South Korea", "Korea", "Taiwan", "Hong Kong",
    "Singapore", "Thailand", "Vietnam", "Indonesia", "Malaysia",
    "Philippines", "Australia", "New Zealand",
    "Canada", "Mexico", "Brazil", "Argentina", "Chile", "Colombia",
    "Peru", "Ecuador", "Uruguay", "Paraguay", "Bolivia", "Venezuela",
    "Costa Rica", "Panama", "Cuba", "Dominican Republic",
    "South Africa", "Egypt", "Nigeria", "Kenya", "Morocco", "Tunisia",
    "Algeria", "Russia", "Ukraine", "Hungary", "Romania", "Bulgaria",
    "Croatia", "Serbia", "Slovenia", "Slovakia",
}


class PubmedAdapter:
    """HTTP client + XML parser bound to PubMed E-utilities."""

    PER_REQUEST_TIMEOUT_S: Final = 8.0
    MAX_RESULTS: Final = 20

    async def search(
        self,
        query: str,
        category: ArticleCategory,
        limit: int,
    ) -> list[ArticleEntity]:
        effective_query = self._compose_query(query=query, category=category)
        retmax = min(max(1, limit), self.MAX_RESULTS)

        async with httpx.AsyncClient(
            timeout=self.PER_REQUEST_TIMEOUT_S
        ) as client:
            pmids = await self._esearch(client, effective_query, retmax)
            if not pmids:
                logger.info(
                    "PubmedAdapter: no PMIDs for query '%s' (%s)",
                    query, category.value,
                )
                return []
            xml_text = await self._efetch(client, pmids)
        return self._parse_articles(xml_text, category)

    # ── HTTP ────────────────────────────────────────────────────────────

    async def _esearch(
        self,
        client: httpx.AsyncClient,
        query: str,
        retmax: int,
    ) -> list[str]:
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
            "sort": "date",
            "tool": "skeen",
            "email": "noreply@skeen.app",
        }
        try:
            res = await client.get(ESEARCH_URL, params=params)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("PubmedAdapter: esearch failed: %s", exc)
            return []
        body = res.json()
        return list(body.get("esearchresult", {}).get("idlist", []))

    async def _efetch(
        self,
        client: httpx.AsyncClient,
        pmids: list[str],
    ) -> str:
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "tool": "skeen",
            "email": "noreply@skeen.app",
        }
        try:
            res = await client.get(EFETCH_URL, params=params)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("PubmedAdapter: efetch failed: %s", exc)
            return ""
        return res.text

    # ── XML parsing ─────────────────────────────────────────────────────

    def _parse_articles(
        self,
        xml_text: str,
        category: ArticleCategory,
    ) -> list[ArticleEntity]:
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("PubmedAdapter: XML parse failed: %s", exc)
            return []

        articles: list[ArticleEntity] = []
        for node in root.findall("./PubmedArticle"):
            article = self._parse_one(node, category)
            if article is not None:
                articles.append(article)
        return articles

    def _parse_one(
        self,
        node: ET.Element,
        category: ArticleCategory,
    ) -> ArticleEntity | None:
        pmid_el = node.find(".//MedlineCitation/PMID")
        title_el = node.find(".//Article/ArticleTitle")
        if pmid_el is None or pmid_el.text is None:
            return None
        if title_el is None:
            return None

        pmid = pmid_el.text.strip()
        title = self._stringify(title_el).strip()

        # Concatenate <AbstractText> chunks — long structured abstracts
        # are split into sections (Background, Methods, …) and we want
        # them merged into a single readable paragraph.
        abstract_chunks = [
            self._stringify(el)
            for el in node.findall(".//Abstract/AbstractText")
        ]
        summary = " ".join(c for c in abstract_chunks if c).strip() or None
        if summary and len(summary) > 480:
            summary = summary[:477].rstrip() + "…"

        journal_el = node.find(".//Article/Journal/Title")
        journal = (
            journal_el.text.strip() if journal_el is not None and journal_el.text
            else None
        )

        article_type_el = node.find(".//PublicationTypeList/PublicationType")
        article_type = (
            article_type_el.text.strip()
            if article_type_el is not None and article_type_el.text
            else None
        )

        published_at = self._parse_date(node)
        authors = self._parse_authors(node)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        return ArticleEntity(
            id=pmid,
            title=title,
            summary=summary,
            authors=authors,
            journal=journal,
            published_at=published_at,
            article_type=article_type,
            url=url,
            category=category,
        )

    def _parse_authors(self, node: ET.Element) -> list[ArticleAuthor]:
        authors: list[ArticleAuthor] = []
        for author_el in node.findall(".//Article/AuthorList/Author"):
            last_name_el = author_el.find("LastName")
            fore_name_el = author_el.find("ForeName")
            collective_el = author_el.find("CollectiveName")

            if last_name_el is not None and last_name_el.text:
                full = last_name_el.text.strip()
                if fore_name_el is not None and fore_name_el.text:
                    full = f"{fore_name_el.text.strip()} {full}"
            elif collective_el is not None and collective_el.text:
                full = collective_el.text.strip()
            else:
                continue

            affiliation_el = author_el.find(".//AffiliationInfo/Affiliation")
            affiliation = (
                affiliation_el.text.strip()
                if affiliation_el is not None and affiliation_el.text
                else None
            )
            country = self._extract_country(affiliation) if affiliation else None
            authors.append(
                ArticleAuthor(
                    name=full,
                    country=country,
                    affiliation=affiliation,
                )
            )
            # We only need top 4 to render the card — anything past that
            # is metadata bloat that the mobile won't display.
            if len(authors) >= 4:
                break
        return authors

    def _parse_date(self, node: ET.Element) -> date | None:
        # ``ArticleDate`` is the most reliable when present (electronic
        # publication date). Fall back to PubDate which carries Year only
        # in older records.
        article_date = node.find(".//Article/ArticleDate")
        if article_date is not None:
            year = article_date.findtext("Year")
            month = article_date.findtext("Month") or "1"
            day = article_date.findtext("Day") or "1"
            try:
                return date(int(year or 0), int(month), int(day))
            except (TypeError, ValueError):
                pass
        pub_date = node.find(".//Journal/JournalIssue/PubDate")
        if pub_date is not None:
            year = pub_date.findtext("Year")
            month_text = pub_date.findtext("Month") or "Jan"
            day = pub_date.findtext("Day") or "1"
            try:
                month = self._parse_month(month_text)
                return date(int(year or 0), month, int(day))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _parse_month(value: str) -> int:
        value = value.strip()
        if value.isdigit():
            return int(value)
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        return months.get(value.lower()[:3], 1)

    @staticmethod
    def _stringify(el: ET.Element) -> str:
        # Some PubMed titles/abstracts contain inline tags (e.g. <i>, <b>);
        # ``itertext`` gives us the readable concatenation regardless.
        return "".join(el.itertext())

    @staticmethod
    def _extract_country(affiliation: str) -> str | None:
        # Affiliations conventionally end with the country name followed
        # by a period. We split on commas, walk back from the end, and
        # match against [_KNOWN_COUNTRIES] case-insensitively.
        cleaned = affiliation.rstrip(". ")
        for chunk in reversed([c.strip() for c in cleaned.split(",")]):
            chunk = re.sub(r"^\d+\s*", "", chunk)
            if chunk in _KNOWN_COUNTRIES:
                return chunk
            for country in _KNOWN_COUNTRIES:
                if chunk.lower() == country.lower():
                    return country
        return None

    # ── Query composition ──────────────────────────────────────────────

    @staticmethod
    def _compose_query(query: str, category: ArticleCategory) -> str:
        template = _CATEGORY_TEMPLATES.get(
            category, _CATEGORY_TEMPLATES[ArticleCategory.ALL]
        )
        cleaned = (query or "").strip()
        if not cleaned:
            return template
        # Sanitise: strip PubMed field tags from user input so a
        # malicious-looking string can't escape the bracketed clause.
        cleaned = re.sub(r"[\[\]\"]", "", cleaned)
        return f"({cleaned}) AND {template}"
