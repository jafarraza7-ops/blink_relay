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
    """Extract and normalize keywords from text.

    Filters for meaningful terms:
    - At least 3 characters long
    - Excludes common stop words and function words
    - Excludes common domain words that appear in most tickets
    """
    if not text:
        return set()

    text = text.lower()
    # Remove special chars, split on whitespace/punctuation
    words = re.findall(r"\b\w+\b", text)

    # Comprehensive stop words and common generic terms
    stop_words = {
        # Articles and prepositions
        "a", "an", "and", "the", "is", "are", "for", "to", "of", "in", "on",
        "at", "by", "with", "or", "as", "be", "from", "it", "this", "that",
        "we", "our", "can", "has", "have", "been", "need", "will", "should",
        "would", "could", "get", "got", "make", "made", "do", "does", "did",
        "not", "no", "yes", "where", "when", "how", "why", "which", "what",
        # Common request/ticket words that appear everywhere
        "request", "ticket", "issue", "system", "user", "data", "feature",
        "bug", "error", "fix", "add", "update", "change", "improve", "new",
        "able", "help", "need", "want", "like", "use", "work", "allow",
        "follow", "process", "workflow", "status", "time", "day", "way",
        "thing", "try", "set", "see", "check", "find", "give", "allow",
        "provide", "better", "information", "important", "different",
    }

    # Extract keywords: 3+ chars, not in stop words
    keywords = {w for w in words if len(w) > 2 and w not in stop_words}

    # Filter out very common words that appear in most tickets
    if len(keywords) > 0:
        # Keep only keywords that are more specific/meaningful
        keywords = {w for w in keywords if not any(
            common in w for common in ['request', 'ticket', 'issue']
        )}

    return keywords


def _jaccard_similarity(keywords1: set[str], keywords2: set[str]) -> float:
    """Calculate Jaccard similarity (intersection / union).

    Returns a score between 0 and 1 where:
    - 1.0 = perfect match
    - 0.0 = no overlap
    """
    if not keywords1 or not keywords2:
        return 0.0
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    return intersection / union if union > 0 else 0.0


def _weighted_similarity(
    ref_title: str,
    ref_problem: Optional[str],
    ref_area: Optional[str],
    cand_title: str,
    cand_problem: Optional[str],
    cand_area: Optional[str],
) -> float:
    """Calculate weighted similarity across multiple fields.

    Weights:
    - Title: 50% (most important, defines the request)
    - Business problem: 35% (explains the need)
    - Affected area: 15% (context)

    Returns a score 0-1 where only high-confidence matches (>0.4) are meaningful.
    """
    # Extract keywords from each field
    title_sim = _jaccard_similarity(
        _extract_keywords(ref_title),
        _extract_keywords(cand_title)
    )

    problem_sim = _jaccard_similarity(
        _extract_keywords(ref_problem),
        _extract_keywords(cand_problem)
    )

    area_sim = _jaccard_similarity(
        _extract_keywords(ref_area),
        _extract_keywords(cand_area)
    )

    # Weighted average with emphasis on title match
    weighted_score = (
        title_sim * 0.50 +  # Title is most important
        problem_sim * 0.35 +  # Problem is secondary
        area_sim * 0.15  # Area is tertiary
    )

    return weighted_score


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

    # Query all requests with same pod and type (excluding only the reference request itself)
    # Include all statuses so users can see similar tickets regardless of progress
    # Note: We filter by pod and request_type to ensure we're comparing like with like
    try:
        result = await db.execute(
            select(Request).where(
                and_(
                    Request.id != ref_req_id,
                    Request.pod == ref_req.pod,
                    Request.request_type == ref_req.request_type,
                )
            )
        )
        candidates = result.scalars().all()
    except Exception as e:
        # If there's an issue loading candidates (e.g., enum deserialization),
        # return empty list instead of failing
        logger.warning(f"Could not load candidate requests for similarity matching: {e}")
        return []

    # Score each candidate using weighted field similarity
    similarities = []
    min_similarity_threshold = 0.40  # Only include matches with >40% similarity

    for candidate in candidates:
        # Calculate weighted similarity across title, problem, and area
        score = _weighted_similarity(
            ref_req.title,
            ref_req.business_problem,
            ref_req.affected_area,
            candidate.title,
            candidate.business_problem,
            candidate.affected_area,
        )

        # Only include if score exceeds minimum threshold
        # This filters out false positives and low-confidence matches
        if score >= min_similarity_threshold:
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
