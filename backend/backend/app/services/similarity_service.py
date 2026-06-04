"""Similarity matching service for finding related requests.

Finds similar requests by keyword matching on title, business_problem, and affected_area.
Uses Jaccard similarity (intersection/union of keywords) for scoring.
"""
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Request, RequestStatus

logger = logging.getLogger(__name__)


@dataclass
class SimilarRequest:
    """A request similar to the query request."""

    id: str
    reference_id: str
    title: str
    pod: str
    status: str
    similarity_score: float


def _extract_keywords(text: Optional[str]) -> set[str]:
    """Extract and normalize keywords from text."""
    if not text:
        return set()

    text = text.lower()
    # Remove special chars, split on whitespace/punctuation
    words = re.findall(r"\b\w+\b", text)
    # Filter out common stop words
    stop_words = {
        "a",
        "an",
        "and",
        "the",
        "is",
        "are",
        "for",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "with",
        "or",
        "as",
        "be",
        "from",
        "it",
        "this",
        "that",
        "we",
        "our",
        "can",
        "has",
        "have",
        "been",
        "need",
    }
    return {w for w in words if len(w) > 2 and w not in stop_words}


def _jaccard_similarity(keywords1: set[str], keywords2: set[str]) -> float:
    """Calculate Jaccard similarity (intersection / union)."""
    if not keywords1 or not keywords2:
        return 0.0
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    return intersection / union if union > 0 else 0.0


async def find_similar_requests(
    db: AsyncSession, request_id: str, limit: int = 5
) -> list[SimilarRequest]:
    """Find requests similar to the given request.

    Args:
        db: Database session
        request_id: UUID of the request to find similar requests for
        limit: Max number of similar requests to return

    Returns:
        List of SimilarRequest, sorted by similarity score (highest first)
    """
    # Load the reference request
    try:
        ref_req_id = uuid.UUID(request_id)
    except (ValueError, AttributeError):
        return []

    result = await db.execute(select(Request).where(Request.id == ref_req_id))
    ref_req = result.scalar_one_or_none()
    if not ref_req:
        return []

    # Extract keywords from reference request
    ref_keywords = _extract_keywords(ref_req.title)
    ref_keywords.update(_extract_keywords(ref_req.business_problem))
    ref_keywords.update(_extract_keywords(ref_req.affected_area))

    if not ref_keywords:
        return []

    # Query all requests with same pod and type (excluding the reference request and completed tickets)
    try:
        result = await db.execute(
            select(Request).where(
                and_(
                    Request.id != ref_req_id,
                    Request.pod == ref_req.pod,
                    Request.request_type == ref_req.request_type,
                    Request.status.not_in([RequestStatus.COMPLETED, RequestStatus.CLOSED]),
                )
            )
        )
        candidates = result.scalars().all()
    except Exception as e:
        # If there's an issue loading candidates (e.g., enum deserialization),
        # return empty list instead of failing
        logger.warning(f"Could not load candidate requests for similarity matching: {e}")
        return []

    # Score each candidate
    similarities = []
    for candidate in candidates:
        cand_keywords = _extract_keywords(candidate.title)
        cand_keywords.update(_extract_keywords(candidate.business_problem))
        cand_keywords.update(_extract_keywords(candidate.affected_area))

        if not cand_keywords:
            continue

        score = _jaccard_similarity(ref_keywords, cand_keywords)
        if score > 0:  # Only include if there's some overlap
            similarities.append(
                SimilarRequest(
                    id=str(candidate.id),
                    reference_id=candidate.reference_id or str(candidate.id),
                    title=candidate.title,
                    pod=candidate.pod,
                    status=candidate.status.value,
                    similarity_score=round(score * 100, 1),
                )
            )

    # Sort by score descending and return top N
    similarities.sort(key=lambda x: x.similarity_score, reverse=True)
    return similarities[:limit]
