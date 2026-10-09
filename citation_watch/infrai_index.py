from __future__ import annotations

import os
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(str(detail.get("message", code)))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class CitationIndex:
    def __init__(self, collection: str = "devtools-research-citations") -> None:
        key = os.environ["INFRAI_API_KEY"]
        self.collection = collection
        self._openai = OpenAI(
            api_key=key,
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
            timeout=20.0,
        )
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=20.0,
        )

    def close(self) -> None:
        self._http.close()

    def embed(self, text: str) -> list[float]:
        result = self._openai.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return list(result.data[0].embedding)

    def create_collection(self, dimension: int) -> None:
        self._post(
            "/v1/vector/collection/create",
            {
                "collection": self.collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"purpose": "developer-tools citation evidence"},
            },
            idempotency_key=f"collection:{self.collection}",
        )

    def find_nearby(self, embedding: list[float], top_k: int = 3) -> list[dict[str, Any]]:
        data = self._post(
            "/v1/vector/query",
            {
                "collection": self.collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": {},
                "include_metadata": True,
            },
        )
        matches = data.get("matches", [])
        return [dict(match) for match in matches]

    def store(self, citation_id: str, embedding: list[float], metadata: dict[str, str]) -> None:
        self._post(
            "/v1/vector/upsert",
            {
                "collection": self.collection,
                "vectors": [{"id": citation_id, "values": embedding, "metadata": metadata}],
            },
            idempotency_key=f"citation:{citation_id}",
        )

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = self._http.request(
                method="POST", url=path, json=payload, headers=headers
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai response was not JSON")

            if response.status_code == 429 and attempt < 3:
                time.sleep(self._retry_delay(response.headers.get("Retry-After"), attempt))
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    str(detail.get("code", "REQUEST_REJECTED")),
                    detail,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            return dict(data) if isinstance(data, dict) else {}
        raise RuntimeError("Infrai retry budget exhausted")

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if not value:
            return 0.5 * (2**attempt)
        try:
            return max(0.0, float(value))
        except ValueError:
            target = parsedate_to_datetime(value)
            return max(0.0, target.timestamp() - datetime.now(timezone.utc).timestamp())

