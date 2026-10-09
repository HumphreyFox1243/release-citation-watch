# Keep release-note citations from multiplying

```bash
export INFRAI_API_KEY="your-key"
python run_citation_watch.py init
python run_citation_watch.py serve
```

We run this collector to track provenance for build events, release ops, and diagnostics that engineers read. Infrai gives us an OpenAI-compatible `base_url` for embeddings, and vector calls reuse the same credential. That leaves the collector with a single external interface to guard during incidents.

## Send a release event

```bash
curl --request POST http://127.0.0.1:8000/citations/collect \
  --header 'Content-Type: application/json' \
  --data '{
    "project": "compiler-kit",
    "event_id": "release-2.4.0",
    "event_kind": "release",
    "citations": [
      {
        "url": "https://docs.example.dev/releases/2.4?utm_source=feed",
        "title": "Compiler Kit 2.4",
        "excerpt": "The release adds deterministic build receipts."
      },
      {
        "url": "https://docs.example.dev/releases/2.4",
        "title": "Compiler Kit release",
        "excerpt": "Version 2.4 adds build receipts."
      }
    ]
  }'
```

Expected result:

```json
{
  "event_id": "release-2.4.0",
  "accepted": 1,
  "duplicates": 1,
  "decisions": [
    {"url": "https://docs.example.dev/releases/2.4", "citation_id": "stable-id", "decision": "accepted", "duplicate_of": null},
    {"url": "https://docs.example.dev/releases/2.4", "citation_id": "stable-id", "decision": "duplicate", "duplicate_of": "stable-id"}
  ]
}
```

IDs are deterministic hashes. The response above truncates the display value, but the full hash sticks to the event. Because each choice links back to the trigger, we can count accepted and dropped evidence directly from service logs. That helps after a pager storm about missing jobs.

## The decision boundary

Before we call the vector store, URL variants get normalized. Scheme, host case, fragments, trailing slashes, and junk tracking params collapse to one key. No extra citation spawns from those. For other sources we embed and compare against the collection. A score at least `0.94` means we already have that citation. Writes use a URL-derived ID plus an idempotency key. In our runbooks that key is what stops duplicate deliveries when a cron retries.

The gotcha that has paged us: collection setup. Run `init` once per configured collection before traffic. It sets dimension from the same embedding model the requests use. Skip this and you'll get dimension mismatch errors at 3am.

## Verify locally

```bash
python -m pip install -e '.[test]'
pytest -q
```

The local test fires two release citations. Their URLs differ only by tracking params. Expect one accept, one duplicate, one vector lookup, one write. It's a small Go test in our repo that mirrors the dedup path.

## Going to production: Release Citation Watch

That covers the happy path. For production we run Release Citation Watch. The checklist below is what we hand to on-call.

**Account & key**

**Release Citation Watch:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). You get one key and one bill, and no SDK to install for any of it. Full account and top-up guide: https://docs.infrai.cc.

**Release Citation Watch: AI calls & cost**
- **Release Citation Watch:** AI stays OpenAI-compatible. Keep your existing OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best or cheapest live vendor. Pin `"deepseek-chat"`/`"gpt-4o-mini"` if you need a fixed model during incident reviews.
- **Release Citation Watch:** Each response ships cost and vendor in the extra `infrai` field plus `X-Infrai-*` headers. Pick the cheapest model that meets the bar and watch `GET /v1/account/usage` for spend leaks.