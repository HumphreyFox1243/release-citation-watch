from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field, HttpUrl


class EventKind(str, Enum):
    BUILD = "build"
    RELEASE = "release"
    DIAGNOSTIC = "diagnostic"


class CitationInput(BaseModel):
    url: HttpUrl
    title: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=2000)


class CollectionRequest(BaseModel):
    project: str = Field(min_length=1, max_length=100)
    event_id: str = Field(min_length=1, max_length=100)
    event_kind: EventKind
    citations: list[CitationInput] = Field(min_length=1, max_length=50)


class CitationDecision(BaseModel):
    url: str
    citation_id: str
    decision: str
    duplicate_of: str | None = None


class CollectionResult(BaseModel):
    event_id: str
    accepted: int
    duplicates: int
    decisions: list[CitationDecision]


TRACKING_KEYS = {"fbclid", "gclid", "ref", "source"}


def canonical_url(raw: str) -> str:
    parts = urlsplit(raw)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def citation_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def collect_citations(
    request: CollectionRequest,
    index: Any,
    similarity_threshold: float = 0.94,
) -> CollectionResult:
    decisions: list[CitationDecision] = []
    seen: dict[str, str] = {}

    for citation in request.citations:
        url = canonical_url(str(citation.url))
        stable_id = citation_id(url)
        if url in seen:
            decisions.append(
                CitationDecision(
                    url=url,
                    citation_id=stable_id,
                    decision="duplicate",
                    duplicate_of=seen[url],
                )
            )
            continue

        evidence = f"{citation.title}\n{citation.excerpt}"
        embedding = index.embed(evidence)
        nearby = index.find_nearby(embedding)
        match = next(
            (item for item in nearby if float(item.get("score", 0.0)) >= similarity_threshold),
            None,
        )
        if match:
            original = str(match["id"])
            seen[url] = original
            decisions.append(
                CitationDecision(
                    url=url,
                    citation_id=stable_id,
                    decision="duplicate",
                    duplicate_of=original,
                )
            )
            continue

        index.store(
            stable_id,
            embedding,
            {
                "url": url,
                "title": citation.title,
                "project": request.project,
                "event_id": request.event_id,
                "event_kind": request.event_kind.value,
            },
        )
        seen[url] = stable_id
        decisions.append(
            CitationDecision(url=url, citation_id=stable_id, decision="accepted")
        )

    accepted = sum(item.decision == "accepted" for item in decisions)
    return CollectionResult(
        event_id=request.event_id,
        accepted=accepted,
        duplicates=len(decisions) - accepted,
        decisions=decisions,
    )
