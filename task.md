# Watch UX Revamp — Task Tracker

Active branch: `feature/watch-ux-revamp`

Direction recorded: practical public-source research before adapter design; disposable research code is acceptable, while production adapters remain bounded and fixture-tested. AI expansion broadens retrieval asynchronously but does not redefine deterministic Watch matching.

## Phase 1 — Fix Watch Creation Bug
- [x] Investigate HTTP/auth layer for Watch creation failure
- [x] Root cause: missing `.env` (backend) and `.env.local` (frontend) for local dev
- [x] Root cause: CSRF `loadCsrfToken()` called `/auth/csrf-token` which fails without session cookie in dev
- [x] Fix: created `.env` with `ALLOW_INSECURE_DEV_AUTH=true`
- [x] Fix: created `apps/web/.env.local` with `DEV_USER_ID`
- [x] Fix: `loadCsrfToken()` returns placeholder in dev mode (backend skips CSRF for dev users)
- [x] Verify frontend production build
- [x] Verify Watch creation persists through the API integration path

## Phase 2 — Backend Schema Evolution
- [x] 2A: Experience level enum (schema + model + migration)
- [x] 2B: search_expansion JSON column (model + migration)
- [x] 2C: Search platform registry (new platforms.py + API endpoint)
- [x] 2D: SearchAdapter/SearchRequest contract (GET or bounded JSON POST)
- [x] Correct migration 0019 to expand/contract and normalize legacy values
- [x] Add server-validated platform_key and enforce 3 platform + 2 custom URL limit
- [x] Hide unimplemented/paused platforms from normal platform endpoint

## Phase R — Practical Retrieval Research
- [x] JobStreet: direct HTTP/SSR feasibility established; browser inspection unavailable
- [x] JobsDB: direct HTTP/SSR feasibility established; browser inspection unavailable
- [x] JobThai: direct HTTP, SSR, GraphQL, and detail feasibility established; browser inspection unavailable
- [x] Capture a sanitized synthetic JobThai fixture for the viable response shape
- [x] Record decisions: JobStreet/JobsDB `PAUSED`; JobThai `DIRECT_HTTP`

## Phase 3 — Static Alias Map
- [x] Create aliases.py with a reviewed mechanical tech-term alias set
- [x] Integrate alias groups into deterministic_match()
- [x] Add tests for positive matches, exclusions, and short-token false positives

## Phase 4 — AI Query Expansion
- [x] Expansion contract (expansion_contracts.py)
- [x] Asynchronous expansion service through AI orchestrator and transactional outbox
- [x] Integrate idempotent request into meaningful Watch create/replace criteria changes
- [x] Use expanded terms for platform retrieval only; preserve deterministic final matching

## Phase 5 — Search Adapters
- [x] SEEK Group research (SSR/Apollo and GraphQL feasibility; terms/robots reviewed)
- [x] SEEK Group adapter decision: paused pending documented permission/API access
- [x] SEEK Group fixture tests: not applicable while paused
- [x] JobThai research
- [x] JobThai adapter implementation
- [x] JobThai fixture tests

## Phase 6 — Frontend UX Revamp
- [x] Platform cards component
- [x] Custom URL auto-detection, with authoritative server-side resolution
- [x] Watch creation form redesign
- [x] Experience level dropdown
- [x] Auto-generated Watch name on the server
- [x] Button wording: "Create Watch"
- [x] Neutral text/initial platform identity cards
- [x] Responsive and accessible styles for new components

## Phase 7 — Production Source Breadth
- [x] Add Remotive as a live, attributed, rate-safe remote-jobs platform
- [x] Share Remotive corpus fetches for six hours to respect its four-requests-per-day guidance
- [x] Expose original source links in Job Inbox
- [x] Add Workable career-page detection and full-description public widget adapter
- [x] Keep JobStreet/JobsDB ingestion paused while permission constraints remain

## Phase 8 — External Search Handoff
- [x] Add owner-scoped external search links derived from a Watch
- [x] Cover SEEK markets, Cambodia local boards, Dice, Welcome to the Jungle, LinkedIn, and Indeed
- [x] Make third-party navigation and data handoff explicit in the UI
- [x] Do not fetch, proxy, store, or present external-site results as DireHire matches

## Future — Fixture Demo (Deferred)
- [ ] Add an optional fixture-powered interactive portfolio/demo mode after production launch
- [ ] Keep demo data synthetic, deterministic, and visibly labeled
- [ ] Keep fixture demo code outside the production discovery path and disabled by default

Current priority: production delivery through live platforms, supported ATS feeds, and external
search handoff. Test fixtures remain in CI for parser reliability; they are not a user-facing mode.

## Verification — 2026-08-13

- [x] `uv run ruff check apps/api/src tests migrations`
- [x] Full backend suite: 116 tests passed
- [x] Frontend ESLint and TypeScript checks
- [x] Next.js production static build (12/12 pages)
- [x] OpenAPI export and TypeScript client regeneration
- [x] Terraform formatting check
- [x] PostgreSQL migration smoke: base → head → 0018 → head in an isolated temporary database
- [ ] Visual browser walkthrough of the local Watch form — deferred because the in-app browser sandbox metadata was unavailable in this environment
