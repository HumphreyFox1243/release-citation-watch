from citation_watch.collection_service import CollectionRequest, collect_citations


class RecordingIndex:
    def __init__(self) -> None:
        self.stored: list[tuple[str, dict[str, str]]] = []
        self.queries = 0

    def embed(self, text: str) -> list[float]:
        return [float(len(text))]

    def find_nearby(self, embedding: list[float], top_k: int = 3) -> list[dict]:
        self.queries += 1
        return []

    def store(self, citation_id: str, embedding: list[float], metadata: dict[str, str]) -> None:
        self.stored.append((citation_id, metadata))


def test_tracking_variants_are_one_citation_before_vector_lookup() -> None:
    request = CollectionRequest.model_validate(
        {
            "project": "compiler-kit",
            "event_id": "release-2.4.0",
            "event_kind": "release",
            "citations": [
                {
                    "url": "https://docs.example.dev/releases/2.4/?utm_source=feed",
                    "title": "Compiler Kit 2.4",
                    "excerpt": "The release adds deterministic build receipts.",
                },
                {
                    "url": "https://docs.example.dev/releases/2.4",
                    "title": "Compiler Kit release",
                    "excerpt": "Version 2.4 adds build receipts.",
                },
            ],
        }
    )
    index = RecordingIndex()

    result = collect_citations(request, index)

    assert result.accepted == 1
    assert result.duplicates == 1
    assert result.decisions[1].duplicate_of == result.decisions[0].citation_id
    assert index.queries == 1
    assert len(index.stored) == 1
    assert index.stored[0][1]["event_kind"] == "release"

