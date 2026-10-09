from __future__ import annotations

from fastapi import FastAPI, HTTPException

from citation_watch.collection_service import CollectionRequest, CollectionResult, collect_citations
from citation_watch.infrai_index import CitationIndex, InfraiError

app = FastAPI(title="Release Citation Watch")


@app.post("/citations/collect", response_model=CollectionResult)
def collect(request: CollectionRequest) -> CollectionResult:
    index = CitationIndex()
    try:
        return collect_citations(request, index)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    finally:
        index.close()


def initialize() -> None:
    index = CitationIndex()
    try:
        probe = index.embed("developer tools citation index")
        index.create_collection(len(probe))
    finally:
        index.close()

