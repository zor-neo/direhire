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
- [ ] Verify frontend builds
- [ ] Verify Watch creation persists to DB (needs running stack)

## Phase 2 — Backend Schema Evolution
- [x] 2A: Experience level enum (schema + model + migration)
- [x] 2B: search_expansion JSON column (model + migration)
- [x] 2C: Search platform registry (new platforms.py + API endpoint)
- [ ] 2D: SearchAdapter contract (extend contracts.py)
- [ ] Correct migration 0019 to expand/contract and normalize legacy values
- [ ] Add server-validated platform_key and enforce 3 platform + 2 custom URL limit
- [ ] Hide unimplemented/paused platforms from normal platform endpoint

## Phase R — Practical Retrieval Research
- [ ] JobStreet: inspect direct HTTP and browser responses; record feasibility
- [ ] JobsDB: inspect direct HTTP and browser responses; record feasibility
- [ ] JobThai: inspect direct HTTP and browser responses; record feasibility
- [ ] Capture sanitized research fixtures for viable response paths
- [ ] Record DIRECT_HTTP/BROWSER/LIMITED/PAUSED/RESEARCH_ONLY decision per platform

## Phase 3 — Static Alias Map
- [ ] Create aliases.py with ~100-200 common tech term aliases
- [ ] Integrate into deterministic_match()
- [ ] Add tests for alias expansion matching

## Phase 4 — AI Query Expansion
- [ ] Expansion contract (expansion_contracts.py)
- [ ] Asynchronous expansion service through AI orchestrator and transactional outbox
- [ ] Integrate idempotent request into meaningful Watch create/replace criteria changes
- [ ] Use expanded terms for platform retrieval only; preserve deterministic final matching

## Phase 5 — Search Adapters
- [/] SEEK Group research (JobStreet/JobsDB API endpoints)
- [ ] SEEK Group adapter implementation
- [ ] SEEK Group fixture tests
- [ ] JobThai research
- [ ] JobThai adapter implementation
- [ ] JobThai fixture tests

## Phase 6 — Frontend UX Revamp
- [ ] Platform cards component
- [ ] Custom URL auto-detection
- [ ] Watch creation form redesign
- [ ] Experience level dropdown
- [ ] Auto-generated Watch name
- [ ] Button wording: "Create Watch"
- [ ] Platform identity cards (permitted official assets or neutral text/initial fallback)
- [ ] Styles for new components
