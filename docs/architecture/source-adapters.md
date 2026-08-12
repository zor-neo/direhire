# P0 Source Adapter Policy

Last reviewed: 2026-08-12

DireHire's launch adapters use only documented, public, employer-controlled job feeds. Normal CI parses deterministic synthetic fixtures and never contacts a live source. Runtime fetching uses HTTPS, blocks private-network destinations and redirects, bounds response size and time, and accepts only expected JSON, HTML, or XML media types.

## Launch set

| Adapter | Public endpoint | Notes |
| --- | --- | --- |
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true` | Public GET Job Board API; full content is required. |
| Lever | `api.lever.co/v0/postings/{site}?mode=json` (or EU host) | Published postings only; JSON mode is required. |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{board}` | Published and listed jobs only. |
| Recruitee | `{company}.recruitee.com/api/offers/` | Authorization-free Careers Site API. |
| Personio | `{company}.jobs.personio.de/xml?language=…` | Company Career Site XML feed. |
| Pinpoint | `{company}.pinpointhq.com/jobs.rss` | Public RSS feed documented for external job listings. |

Some feeds omit a separate employer display name. In that case, DireHire displays the public board identifier from the validated endpoint; it does not infer a legal company name.

## Deliberate exclusions

SmartRecruiters and Teamtailor are not in the public launch set because their documented APIs require customer credentials. Login-only sources, undocumented private endpoints, CAPTCHA bypass, imported cookies, and access-control circumvention remain unsupported. If a source changes its access posture or response contract, its circuit should pause it rather than escalating access behavior.

## Contract evolution

Parser changes require sanitized fixture tests. Adding a source requires current official documentation review, capability metadata, strict host/path validation, bounded access behavior, and an operational disable path. Browser rendering is reserved for a separately reviewed adapter and runs only in the bounded Fargate Spot worker.
