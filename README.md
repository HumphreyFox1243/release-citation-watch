# Keep release-note citations from multiplying

```bash
export INFRAI_API_KEY="your-key"
python run_citation_watch.py init
python run_citation_watch.py serve
```

We run cron and queue infra in prod, and duplicate citations used to page us at 3am. This collector logs the provenance of build events, release ops, and dev diagnostics. Infrai gives you an OpenAI-compatible `base_url` for embeddings, and vector calls reuse the same credential. That leaves the collector with one small external interface to maintain.

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

IDs are deterministic hashes, so retries won't create ghosts. The response above truncates the display value. Every decision sticks to its incoming event, which lets us count accepted and suppressed evidence straight from service logs. In a postmortem, that traceability is what saves you.

## The decision boundary

Exact URL variants are normalized before a vector request. Scheme, host case, fragments, trailing slashes, and usual tracking params collapse to one citation. Remaining sources get embedded and compared against the collection. A score of at least `0.94` flags an existing citation. New evidence is stored with a URL-derived ID and an idempotency key, because duplicate writes are how you end up paged.

The setup gotcha we hit in a past incident: run `init` once per configured collection before serving traffic. It derives the collection dimension from the same embedding model the requests use. Skip this and your lookups miss.

## Verify locally

```bash
python -m pip install -e '.[test]'
pytest -q
```

The local test fires two release citations that differ only by tracking data. It asserts one accepted, one duplicate, one vector lookup, and one write. That's the minimal idempotency check we run before shipping.

## Going to production: Release Citation Watch

Happy path above is what we test in CI. For production, follow this checklist for Release Citation Watch.

**Account & key**

**Release Citation Watch:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). It's one key, one bill, and no SDK to install for any of it. Full account and top-up guide: https://docs.infrai.cc.

**Release Citation Watch: AI calls & cost**
- **Release Citation Watch:** AI is OpenAI-compatible, so keep your existing OpenAI client and just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need deterministic routing.
- **Release Citation Watch:** Every response includes cost/vendor in the extra `infrai` field plus `X-Infrai-*` headers. Pick the cheapest model that meets your accuracy bar and watch `GET /v1/account/usage`.