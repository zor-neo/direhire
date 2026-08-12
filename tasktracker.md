# DireHire P0 Task Tracker

Last updated: 2026-08-13

## How to use this file

Read `AGENTS.md`, `projectSpecs.md`, and this file before making a non-trivial change. Update this file in the same change whenever a task is completed, reordered, blocked, or materially redesigned. Keep entries concrete enough that a fresh session can resume without reconstructing context.

## Current state

- Repository began as a greenfield workspace containing only `AGENTS.md` and `projectSpecs.md`.
- Phase 0 foundation now exists: pnpm/Next.js static web app, uv/FastAPI API, SQLAlchemy/Alembic, local PostgreSQL compose service, pinned lockfiles, CI, Terraform scaffold, README, and ADR baseline.
- First vertical slice now works locally: create/list/activate a tenant-owned Watch and request an idempotent manual run; the run and `watch.discovery.requested.v1` outbox event are committed together.
- Phase 1 authentication foundation now implements Cognito Authorization Code + PKCE, strict ID-token verification, opaque hashed backend sessions, CSRF, revocation/expiry, security-version invalidation, bounded last-seen updates, and mandatory MFA gating for privileged roles.
- Phase 0 is complete: OpenAPI and TypeScript contracts are generated and drift-checked, and deterministic synthetic seed/reset tooling is idempotent and production-blocked.
- Phase 1 entitlements and audit are implemented: finite plan limits with user overrides, Watch/manual-run enforcement, owner-only Account Activity, Superadmin-only plan configuration, and append-only sanitized audit events.
- Watch lifecycle/source foundations now support create/read/replace/activate/pause/archive/hard-delete, owned platform/custom sources, public-URL SSRF safeguards, and a fixture-only dedicated adapter.
- Discovery processing now preserves partial source success and creates canonical Job/JobVersion/SourceListing records, deterministic Watch matches, and owner-scoped Inbox items. The outbox dispatcher publishes stable envelopes and leaves failed publications retryable.
- Account-level IANA-timezone scheduling creates idempotent per-Watch/per-day run events. Strict bounded CSV parsing, operational source policy records, and a schema.org-only generic public adapter now cover the remaining source input foundations without live source access in CI.
- The SQS runtime now publishes versioned outbox envelopes, consumes discovery batches with partial-failure responses, and has Terraform-managed per-workload queues, DLQs, redrive policies, encryption, long polling, and queue-age/DLQ alarms.
- Manual runs now have a plan-configured cooldown distinct from daily quota. Source circuits have configurable thresholds/cooldowns, automatic failure and recovery transitions, and audited Superadmin controls without exposing user career content.
- Canonical matching jobs now enqueue one versioned structured analysis through the outbox. Public JD analysis sanitizes contact/markup noise, validates a strict `JobDemandProfile`, performs one bounded repair, uses a health-aware three-project Gemini pool, records provenance/token cost without payload logs, and reuses completed analysis in the owner-scoped Inbox.
- Phase 5 backend flows now provide owner-scoped applications, private notes, interview experience, explicit reminders, one masked account-level Telegram/WhatsApp preference, permanent in-app run digests, idempotent external delivery, and strict no-failover behavior. No-match runs create no external message.
- Phase 6 privacy foundations now provide direct-to-S3 bounded quarantine uploads, real PDF/DOCX structural validation, replaceable ClamAV scanning, clean-only owner downloads, optional manual Profile/Base CV, short-lived private ZIP exports, hard individual CV deletion, durable career-data purge, and irreversible account deletion with immediate session revocation and shared-job preservation.
- Phase 7 private-AI foundations now use an OpenRouter-only ZDR/data-collection-denied route with approved-provider constraints, strict schemas, immutable least-data snapshots, transactional outbox requests, feature-scoped quotas, metering, bounded repair, and no Gemini fallback. Owner-scoped Profile Fit, CV suggestions, tailored-CV content, Prepare to Apply, Career Prep, and Professional Advice artifacts are implemented; Profile suggestions require explicit Accept/Edit/Reject and user edits persist as working drafts.
- Private-AI artifacts are included in owner exports without internal input snapshots and are hard-deleted by career/account deletion. Cross-tenant reads, edits, deletes, enumeration, and Admin access are denied.
- Product scope is P0 as defined in `projectSpecs.md`; P1/P2/Future items remain excluded.
- Versioned tailored-CV drafts now support rename/duplicate/archive/hard-delete plus coalesced private DOCX/PDF generation and owner-only signed downloads. ATS output has structural DOCX/PDF tests; Company Research is available through the private-AI artifact service.
- Analyze-a-Job now supports public URLs and private pasted text with separate privacy routing, quotas, coalescing/idempotency, explicit save/delete/Watch-draft actions, and similar-opening results from the existing corpus.
- Shared public source fetches now use normalized keys, short result caching, leases, and safe retry behavior. Outbox publication records bounded safe failure metadata, and Superadmin operational endpoints expose stuck-work metadata without private payloads.
- Six documented public launch adapters are frozen and fixture-tested: Greenhouse, Lever, Ashby, Recruitee, Personio, and Pinpoint. Credentialed/private platforms remain excluded.
- The complete accessible static UI now covers Watches, Inbox, Analyze a Job, Applications, Career/Profile/CV, notifications, settings, privacy workflows, and privacy-safe Superadmin operations.
- Production packaging and Terraform cover workload-aware Lambda consumers, the scheduled pump, Fargate Spot browser/backup task boundaries, Cognito, S3/CloudFront/OAC, API Gateway, queues/DLQs/alarms, separated IAM, finite logs, budgets, and immutable GitHub OIDC deployment.
- Audited database kill switches protect external/expensive features. Admin operations expose source circuits, stuck work, and 30-day AI token/cost/cache telemetry without private career content.
- A synthetic local PostgreSQL backup/restore drill restored migration `20260812_0018`, one user, one Watch, and eight platform controls into a disposable database; the drill databases were removed afterward.
- P0 implementation and local acceptance verification are complete. Remaining actions are production environment provisioning, reviewed Terraform apply, and post-deploy smoke checks—not application implementation backlog.
- Finalization audit fixed sibling-origin CSRF bootstrap, normalized standard PostgreSQL/Neon URLs to the installed psycopg v3 driver, and replaced invalid empty-payload Lambda console checks with a read-only HTTPS production smoke script.
- The previously empty production Neon database was migrated through Alembic `20260812_0018`; 44 schema tables were verified and no synthetic user data was seeded.
- No production infrastructure has been created or modified.
- No secrets or production data are present.

## Architecture decisions in force

- Modular monolith API plus independently runnable async workers.
- Exactly one PostgreSQL database, accessed through SQLAlchemy repositories/services.
- Important DB-to-queue transitions use a transactional outbox.
- FastAPI OpenAPI is the HTTP contract; routes begin at `/api/v1`.
- Next.js is a static export; it contains no server-side secrets.
- Local and CI data is deterministic and synthetic.
- Authentication uses Cognito Authorization Code + PKCE and opaque backend sessions. Development shortcuts are rejected in production.

## Ordered P0 backlog

### Phase 0 — scaffolding

- [x] Create pnpm/Next.js static frontend workspace.
- [x] Create Python/FastAPI package with uv-compatible `pyproject.toml` and Ruff configuration.
- [x] Add SQLAlchemy, Alembic, local PostgreSQL compose file, and deterministic seed path.
- [x] Add contract generation/check workflow from FastAPI OpenAPI.
- [x] Add Terraform skeleton and CI checks.
- [x] Add README, architecture baseline, and initial ADRs.

### Phase 1 — identity and security

- [x] Cognito PKCE callback and opaque hashed sessions.
- [x] Cookie, CSRF, strict production CORS validation, expiry/revocation, security-version invalidation, and bounded last-seen behavior.
- [x] Roles, plans, configurable entitlements, privileged MFA enforcement.
- [x] Account activity and append-only sanitized audit.
- [x] Cross-tenant security matrix for private resource types implemented so far; extend this continuously as new private resources land.

### Phase 2 — Watch/source/discovery

- [x] Watch lifecycle and stable Target/Required/Exclude semantics.
- [x] Source definitions, policy/capability metadata, custom URL and CSV validation.
- [x] Dedicated fixture-backed adapters plus safe generic public adapter.
- [x] Scheduled/manual run creation, idempotency, cooldown, partial-success history.

### Phase 3 — corpus and async reliability

- [x] Canonical Job/JobVersion/UserJob model and conservative exact-identity deduplication.
- [x] Durable workflow entities and explicit versioned event contracts.
- [x] Transactional outbox dispatcher, SQS/DLQ configuration, idempotent consumers.
- [x] Fetch coalescing, correlation propagation, stuck-work visibility.

### Phase 4 — public AI and inbox

- [x] Versioned `JobDemandProfile` schema and sanitizer.
- [x] Provider-neutral AI orchestrator with strict public/private classification.
- [x] Three-project Gemini health-aware round robin, validation, cache, metering.
- [x] Deterministic Watch matching before AI; Inbox never hides explicit matches.

### Phase 5 — notifications and applications

- [x] In-app notification source of truth and one digest per Watch run.
- [x] One account-level Telegram or WhatsApp channel with no silent failover.
- [x] User-owned application states, notes, interview details, and reminders.

### Phase 6 — private files/profile/CV

- [x] Quarantine/validate/scan PDF and DOCX uploads.
- [x] Owner-authorized short-lived S3 downloads and cross-tenant tests.
- [x] Optional Profile and Base CV flows; core remains usable without either. (CV-assisted suggestions remain part of the private AI increment.)
- [x] Durable export, career-data deletion, and account deletion workflows.

### Phase 7 — premium private AI

- [x] OpenRouter-only private route with privacy restrictions and no public fallback.
- [x] Owner-scoped structured Profile comparison, CV suggestions, tailored-CV content, Prepare to Apply, interview prep, and Professional Advice.
- [x] Versioned ATS-friendly tailored CV drafts with private DOCX/PDF generation/download and explicit Company Research.

### Phase 8 — operations and hardening

- [x] Admin operational API and UI views that never expose private career bodies.
- [x] Kill switches, quotas, circuits, alarms, finite retention, and cost analytics.
- [x] Backup/restore drill, immutable rollback path, runbooks, and full local P0 acceptance pass.

## Current work session

- [x] Read `projectSpecs.md` and `AGENTS.md`.
- [x] Inventory repository and available local tooling.
- [x] Complete Phase 0 foundation.
- [x] Implement and verify the first Watch vertical slice.
- [x] Implement and verify the Cognito/opaque-session security slice.
- [x] Implement and verify entitlements, Account Activity, and append-only audit.
- [x] Generate OpenAPI/TypeScript contracts and deterministic synthetic seed/reset tooling.

## Deployment Status

- [x] Initialized GitHub repository and set up AWS billing.
- [x] Provisioned Neon PostgreSQL database and updated SSM secrets.
- [x] Configured Cloudflare domain (`zorneo.dev`) and requested ACM Certificates.
- [x] Pushed runtime, backup, and browser-worker Docker images to ECR.
- [x] Applied Terraform to deploy AWS backend (API Gateway, Cognito, SQS, Lambdas).
- [x] Resolved new account Lambda concurrency limit errors and Docker manifest issues.
- [x] Generated `.env.production` with Cognito and API Gateway outputs.
- [x] Built Next.js static output locally (`npm run build`).
- [x] User is modifying frontend UI to satisfaction before final deployment to S3.
- [x] Sync UI build to S3 and invalidate CloudFront cache.
- [x] Apply and verify production database migrations at Alembic head `20260812_0018`.
- [ ] Final smoke check and testing.

## Verification log

- `python -m ruff format .` — passed.
- `python -m ruff check .` — passed.
- `python -m uv run pytest` — 88 passed (tenant isolation, deletion, idempotency, outbox, public/private AI routing, cross-origin CSRF bootstrap, tailored documents, Analyze-a-Job, coalescing, kill switches, worker routing, and launch-adapter fixtures).
- `corepack pnpm lint` — passed.
- `corepack pnpm typecheck` — passed.
- `corepack pnpm build` — passed; 12 static pages generated across all P0 product and operational routes.
- `corepack pnpm audit --prod` — no known vulnerabilities after upgrading to Next.js 16.3.0.
- Python dependencies are pinned in `uv.lock`; FastAPI 0.141.1 and Starlette 1.6.0 replaced a vulnerable framework line, and `pip-audit` reports no known vulnerabilities. CI enforces the Python audit.
- Alembic upgrade from base through `20260812_0018` and downgrade back to base against a disposable SQLite database — passed.
- OpenAPI JSON and TypeScript types regenerate successfully; frontend imports the generated Watch contract.
- Synthetic seed create/idempotent rerun/reset smoke check — passed with exactly one fictional user and Watch.
- `terraform fmt -check -recursive infrastructure/terraform`, `terraform init -backend=false`, and `terraform validate` — passed with AWS provider 6.58.0.
- Lockfile-driven API runtime and browser-worker image builds plus the pinned Debian PostgreSQL/AWS CLI backup image build — passed. Runtime smokes confirmed FastAPI 0.141.1, Starlette 1.6.0, Mangum, Playwright 1.55.0, the locked AWS SDK graph, AWS CLI 2.28.18, and `pg_dump` 17.6.
- High-confidence repository secret-pattern scan — passed; no secrets found outside excluded dependency/build directories.
- Local synthetic PostgreSQL logical backup/restore drill — passed and recorded in `docs/operations/restore-drills.md`.
- In-app browser visual bootstrap was unavailable because the integration rejected required sandbox metadata. Semantic accessibility, lint, type, and static-render gates passed; visual production smoke remains on the first-deployment checklist.
- Read-only production HTTPS smoke passed for frontend/security headers, API health, credentialed CORS, protected-route error handling, and Cognito authorization-code + PKCE initiation. Authenticated login/mutation, Inbox, and private-file ownership remain on the final human walkthrough.

## Known environment notes

- Python 3.13 and Node.js 22 are installed.
- `uv` 0.8.15 is installed as a Python user tool; invoke it as `python -m uv` if the user scripts directory is not on `PATH`.
- pnpm is available through Corepack; the repository pins pnpm 10.15.0.
- Terraform is installed.
- The workspace is not yet a Git repository.
