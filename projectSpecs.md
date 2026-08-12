# projectSpecs.md

> **Project:** Production-minded AI Job Search Automation Platform  
> **Status:** P0 implementation specification  
> **Date:** 2026-08-11  
> **Goal:** Build a real, low-cost, multi-user job-search automation product that is useful by itself and also demonstrates sound AWS/cloud engineering.  
> **Rule:** Production-minded does not mean over-engineered. Build strong P0 foundations, but do not silently implement P1/P2/Future ideas.

---

# 1. Product Vision

The product automates repetitive job discovery and makes each matched job easier to understand and act on.

The non-negotiable core flow is:

**Sources → scheduled discovery → normalize/deduplicate → deterministic Watch matching → holistic AI JD analysis → Job Inbox → optional external digest → user-controlled tracking**

The core product must work with **no Professional Profile and no CV**.

Optional/premium layers enrich the core:

- Professional Profile → job-vs-user comparison/readiness
- Base CV → truthful tailored CV drafts
- Real-work sanity check → realistic scenarios
- Professional Advice → what to improve and what not to waste time on
- Prepare to Apply → messages/cover letter/checklist
- Career Prep → interview prep, company research, practice scenarios
- Future semantic matching → overcome literal keyword weaknesses

**Job Watch intent remains the strongest signal.** AI Profile Fit may enrich or rank, but must never silently hide a job that explicitly matched the Watch.

---

# 2. Scope Levels

Every requirement is one of:

- **P0 — Production MVP:** required before first real-user release.
- **P1 — Early Production:** add after observing initial real usage.
- **P2 — Growth:** add when scale/revenue/operations justify it.
- **Future / Architectural Provision:** do not implement now; ensure P0 does not block it.

Nothing becomes P0 simply because it sounds useful.

---

# 3. Product Principles

## 3.1 Free must be valuable

Free should complete:

**Find → Understand → Notify → Track**

Premium adds:

**Personalize → Compare → Prepare → Improve**

Do not deliberately make Free frustrating.

## 3.2 Progressive disclosure

Show only what is needed for the next decision.

Avoid dense default views, giant analytics pages, dozens of toggles, or exposed AI configuration.

## 3.3 Reduce decision fatigue

The system chooses sensible professional defaults.

Do not ask users to choose:

- AI provider/model
- reasoning depth
- writing tone/style
- scraper mode
- retry policy
- platform-specific technical parameters

The user chooses intent; the system chooses implementation.

## 3.4 Calm UX

No streaks, job-seeker rankings, rejection pressure, “falling behind” messages, interview performance scores, or permanent negative dashboards.

## 3.5 Accessibility

P0 aims for practical WCAG 2.2 AA-aligned implementation:

- semantic HTML
- keyboard use
- visible focus
- accessible labels
- responsive layouts
- no color-only status meaning
- accessible dialogs/tooltips
- reasonable contrast

---

# 4. Main Navigation

Recommended P0 navigation:

- Dashboard
- Job Watches
- Job Inbox
- Analyze a Job
- Applications
- Professional Profile
- CVs
- Career Prep ✦
- Settings

Admin is separate and role-gated.

For Free, Career Prep is visible but subdued rather than hidden behind many padlocks.

Dashboard is action-oriented:

- new jobs
- active Watches
- application status summary
- next automatic search
- Run now
- important warnings

---

# 5. Accounts, Roles, Plans, Entitlements

P0 is **multi-user from Day 1**.

Roles and plans are separate:

```text
role = USER | ADMIN | SUPERADMIN
plan = FREE | PREMIUM
```

## USER

Normal product access.

## ADMIN

Operational access only, such as:

- source health
- retries/circuit breakers
- failed runs
- notification health
- user-support metadata
- selected entitlement operations if authorized

## SUPERADMIN

Very limited population, initially possibly one bootstrap account.

May:

- grant/revoke Admin
- manage global operational controls
- manage privileged configuration
- perform emergency controls

Administrative authority does **not** imply routine access to users’ private career data.

## Entitlements

Centrally configurable and never hard-coded.

Possible fields:

```text
plan
plan_source
entitlement_key
limit_value
enabled
effective_from
effective_until
admin_override
```

Possible `plan_source`:

- admin_grant
- future_payment
- future_promotion

Configurable examples:

- active Watch count
- manual run allowance
- scheduled runs/day
- Analyze-a-Job quota
- Base CV count
- CV tailoring quota
- Career Prep quota
- deep reasoning quota
- document generation quota

No “unlimited” promise in P0.

---

# 6. Authentication and Sessions

Use **Amazon Cognito User Pools**.

P0:

- email/password
- email verification
- password reset
- Authorization Code + PKCE
- SSO later

Do not persist long-lived Cognito tokens in `localStorage`.

Use opaque backend-managed sessions:

```text
Cognito login
→ backend callback
→ random session token
→ Secure + HttpOnly browser cookie
→ store only token hash + metadata in PostgreSQL
```

Suggested `auth_session`:

- id
- token_hash
- user_id
- created_at
- expires_at
- last_seen_at
- revoked_at
- security_version

Use bounded last-seen updates, not a DB write per request.

P0 MFA:

- mandatory for ADMIN
- mandatory for SUPERADMIN
- optional for USER
- step-up/recent authentication for highly sensitive privileged changes where appropriate

Cookie/session safeguards:

- Secure
- HttpOnly
- appropriate SameSite
- CSRF protection for cookie-authenticated mutations
- strict production CORS
- HTTPS only
- no tokens in URLs
- no auth secrets in logs

---

# 7. Onboarding

Minimal signup.

After verification:

```text
Personalize your job matches

Add a Professional Profile and/or Base CV for
job-vs-you comparison, fit analysis, advice and CV tailoring.

[Build Profile] [Upload CV] [Skip for now]
```

Skipping is accepted without guilt or repeated nagging.

Then:

**Create first Job Watch → Activate & Run now**

Profile/CV reminders appear only when relevant.

---

# 8. Job Watch

First-class object.

Lifecycle:

```text
DRAFT → ACTIVE → PAUSED → ARCHIVED
```

Deletion is a separate destructive action.

Rules:

- only Active runs automatically
- Draft may be incomplete
- Paused preserves config/history
- Archived hidden from normal active view
- explicit Delete follows deletion policy

Universal Watch form across sources.

Fields/concepts:

- supported source selections
- custom URLs
- target terms
- required terms
- excluded terms
- locations
- work arrangement
- employment type
- experience target
- posting age
- raw natural-language intent
- optional advanced constraints

### Work arrangement

- On-site
- Hybrid
- Remote

### Employment type

- Full-time
- Part-time
- Contract
- Temporary
- Internship
- Freelance / Project

### Target / Required / Exclude

- **Target:** broadens; related to at least one may match
- **Required:** narrows; must satisfy
- **Exclude:** removes

Do not require Boolean syntax.

Normalize aliases/variants before future semantic matching.

### Experience

Strategic signal, not a hard cutoff.

Possible labels:

- Within Target
- Reasonable Stretch
- Substantial Gap

A Watch-matched job stays visible even with a large gap.

### Posting age

Default 30 days.

Options:

- 3
- 7
- 14
- 30
- Any available

If employer date is unavailable, do not automatically discard.

### Salary

Extract and normalize only if employer states it.

Preserve raw value.

P0 salary is informational only and never a deciding Watch filter.

Never invent salary as employer data.

### Schedule/work hours

Extract stated evening/weekend/shift/on-call/hours/travel details.

Do not add schedule-availability filtering to P0 Watch UI.

---

# 9. Location, Remote Eligibility, Work Authorization

Preserve raw employer location and normalized hierarchy.

Work arrangement and remote geographic eligibility are separate.

Remote eligibility:

- Worldwide
- Country-restricted
- Region-restricted
- Timezone-restricted
- Work-authorization-restricted
- Unclear

Remote never means worldwide by assumption.

Work-authorization status:

- Explicitly Open
- Sponsorship Available
- Existing Work Authorization Required
- No Sponsorship
- Local/Nationality Only
- Unclear

Absence of sponsorship wording means **Unclear**, not expat-friendly.

Optional Profile fields may include:

- nationality/citizenship
- countries with current work authorization
- sponsorship needed yes/no/prefer not

Never infer these from name, language, current location, photo, or CV appearance.

Strategic feasibility signals can consider:

1. nationality/citizenship restrictions
2. work authorization/sponsorship
3. mandatory licenses
4. language
5. experience
6. education
7. skills/readiness

---

# 10. Source UX and Adapter Model

Users can mix:

1. major supported platform cards
2. custom public listing/search URLs
3. company careers URLs
4. CSV bulk input

Individual JD URLs belong primarily to **Analyze a Job**.

Major platforms use logo cards with no URL required.

Selected sources display as removable chips.

Bulk input is supported but hidden until requested.

### Source tiers

- **Tier A:** dedicated adapter
- **Tier B:** generic public source adapter
- **Tier C:** unsupported/private/login-only/strong anti-automation

P0 does not promise autonomous careers-page discovery from arbitrary homepages.

### Adapter interface

Conceptually:

```text
validate_source()
discover_jobs()
fetch_job_detail()
normalize_job()
health_check()
```

Capability metadata can cover:

- pagination
- keyword/location search
- direct HTTP
- browser required
- full JD
- rate limits
- freshness

### Responsible access

Preferred:

```text
official/public API
→ public HTTP
→ browser rendering only when needed
```

Never implement:

- CAPTCHA bypass
- external password collection
- imported browser cookies
- stolen/private session tokens
- access-control circumvention
- hidden/private endpoint abuse

If access becomes questionable, degrade/pause/disable rather than escalate aggressively.

Before supported-source list is frozen, research current source activity/accessibility. Prefer roughly 6–10 excellent tested launch adapters, disproportionately useful for SEA plus important global sources.

---

# 11. Source Sharing, Coalescing, Protection

Avoid duplicate public fetches.

Normalize:

```text
source_fetch_key =
adapter + normalized listing URL + relevant search params
```

If same public fetch is queued/running/recently successful, coalesce/reuse where safe.

Private user intent remains private.

Controls:

- global scraper concurrency
- per-source/adapter concurrency
- configurable rate limits/delays
- circuit breaker
- retries
- DLQ
- source health

Health:

```text
HEALTHY → DEGRADED → TEMPORARILY_PAUSED
```

One bad source does not block the whole Watch.

Browser per-source concurrency can initially be very conservative, often 1.

---

# 12. Scheduling and Run Behavior

P0 uses one **account-level daily scheduled time**.

All active Watches run at that user time.

Timezone:

- initial suggestion from browser/IP
- stored as IANA timezone, e.g. `Asia/Bangkok`
- DB timestamps UTC
- UI converts

### Run now

Uses the same pipeline as scheduled runs.

Server-side:

- auth
- entitlement
- cooldown
- concurrency
- idempotency

Repeated clicks while active should return existing run.

Platform/source failures should not unfairly consume allowance.

### No-match run

No Telegram/WhatsApp message by default.

Run still recorded in app.

### User run history

Show summary first:

- last search
- status
- matches
- next run
- warnings

Deeper details on request:

- sources checked
- listings discovered
- valid jobs
- prior known
- new notifications
- duration

No stack traces.

Detailed operational history can be ~90 days, then compact aggregates.

---

# 13. Durable Workflow State

P0 uses PostgreSQL-backed workflow state + SQS workers, **not Step Functions**.

Entities can include:

- JobWatchRun
- SourceFetch
- ScrapeTask
- AIAnalysisOperation
- NotificationOperation
- DocumentOperation

Status model:

```text
QUEUED
RUNNING
SUCCEEDED
RETRYABLE_FAILED
PERMANENT_FAILED
CANCELLED
```

Run-level outcomes:

- Completed
- Completed with warnings
- Failed

Partial success is first-class.

**Future:** Step Functions may be introduced only if orchestration complexity genuinely warrants it.

---

# 14. Transactional Outbox and Idempotency

For important DB → queue boundaries:

```text
BEGIN
  write business state
  insert OutboxEvent
COMMIT
```

Dispatcher publishes to SQS and marks published.

Requirements:

- stable event IDs
- schema versioning
- retries/backoff
- stuck-outbox monitoring
- DLQs

Consumers remain idempotent because delivery is at-least-once.

Possible idempotency keys:

- discovery_job_id
- canonical_job_id
- jd_version_hash
- ai_analysis_hash
- notification_digest_id
- document_generation_request_id

Before expensive work, check durable completion.

Do not duplicate AI charges, jobs, notifications, or documents under retry.

---

# 15. Workload Priority and Fairness

P0 priorities:

1. interactive AI
2. user-triggered background
3. scheduled discovery
4. maintenance/reprocessing

Notifications should be prompt once result is ready.

Use workload-specific queues and bounded concurrency.

One user must not monopolize processing.

Quotas/cost guardrails override priority.

---

# 16. Canonical Public Job Corpus

Shared public data:

- Job
- JobVersion
- source listings
- reusable public JD analysis

Private user relationships:

- UserJob
- Watch match
- Profile fit
- application
- notes
- notification state
- CV association

Do not duplicate public JD per user.

Pasted private JDs do not enter shared corpus.

---

# 17. Deduplication

Prefer false negatives over false positive merges.

### High confidence

May auto-consolidate, e.g.:

- same employer requisition/job ID
- same company/title/location
- strong content/source identity

### Medium confidence

Do not globally merge.

Show:

> Very similar vacancy found on another source. It may be the same opening. Please verify before applying.

Actions may include Compare/Open Both and private Same/Different judgment.

One user’s decision does not globally rewrite corpus identity.

### Low confidence

Keep separate.

Official employer source may be preferred when confidently same, with “Also found on…” for others.

---

# 18. Job Lifecycle and JobVersion

Job lifecycle:

```text
ACTIVE → UNCERTAIN → NO_LONGER_LISTED
```

One missing scrape does not mean closed.

Source failure is not evidence of vacancy removal.

If found again, job may return Active.

`JobVersion` stores content hash and capture timestamp.

Do not overwrite JD blindly.

Material updates may later create `Job Updated` behavior.

Reposts can be new opportunities when evidence supports it.

---

# 19. Job Inbox

Status-first, grouped by Watch.

Source is secondary metadata.

Clean card:

- title
- company
- location
- match strength label
- recency
- one notable constraint
- View Analysis
- Save / Applied / Ignore

Deeper salary/source/JD/eligibility info appears after opening.

---

# 20. Applications, Notes, Reminders

Application status is user-controlled.

Possible statuses:

- New
- Viewed
- Saved
- Interested
- Applied
- Interviewing
- Offer
- Rejected
- Withdrawn
- Ignored
- Archived

AI never infers stage.

When Applied, date can default to today but is editable.

Interview stage:

- Screening
- Technical
- Final
- Other

### Notes & Experience

Basic private free-form notes for:

- recruiter calls
- salary expectation
- questions
- role details
- follow-up

When Interviewing, optional:

- stage
- date
- questions remembered
- what went well
- what was difficult
- other notes

Recording notes never automatically triggers AI.

### Reminders

P0 in-app only, user-created.

Application:

- 7 days
- 14 days
- choose date
- none

Interview:

- 1 day before
- 3 days before
- choose date
- none

No pressure UX and no automatic reminders.

---

# 21. Notifications

In-app is permanent source of truth.

External optional channels:

- Telegram
- WhatsApp

User chooses **one** external channel account-wide in P0.

Use official direct APIs.

No Twilio/aggregator dependency initially.

One digest per completed Watch run, not one message per job.

No external no-match message by default.

If selected provider fails:

- retry
- do not silently switch channel
- keep result in app
- record delivery state

States can include queued/sent/delivered-if-supported/failed.

---

# 22. Analyze a Job

Separate top-level workflow.

Inputs:

- public job URL
- pasted JD text

No source/model chooser.

### Public URL

Validate/fetch and reuse canonical corpus/analysis where possible.

### Pasted JD

Private by default.

Not shared corpus.

Not a Watch.

Not used for automatic notifications.

After analysis:

- optional Save/Add to records
- show 3–5 strong recent similar openings from corpus
- `Create Job Watch from this` creates Draft only

Free can have a configurable quota.

---

# 23. Professional Profile and Taxonomy

Profile is optional.

Ways to build:

1. manual guided catalog
2. CV-assisted suggestions
3. hybrid

AI suggestions require user Accept/Edit/Reject.

Profile includes:

- competencies
- domain knowledge
- technologies/tools
- languages
- credentials/licenses
- education
- experience
- eligibility/work rights

### Catalog

Maintain own canonical Competency Catalog.

Seed from ESCO + O*NET, but do not treat them as universal truth.

Store:

- canonical concept
- aliases
- source mappings
- related/parent
- translation-compatible structure

Preserve custom user term exactly.

Maintain separate Occupation/Role Catalog.

Always preserve employer raw title.

P0 UI English only; original JD text preserved.

---

# 24. AI JD Analysis

AI must interpret the **whole JD**, not just summarize or count keywords.

Three conceptual passes:

1. holistic role interpretation
2. evidence-level extraction
3. reconciliation

Interpret:

- real role shape
- responsibilities
- ownership
- seniority
- core vs incidental
- required vs preferred
- blockers
- repeated themes
- contradictions
- uncertainty

Example:

- “Remote” + “must reside in Germany” → Remote, Germany-only
- “Entry-level” + “5 years minimum” → explicit inconsistency

---

# 25. Structured JobDemandProfile

Structured object is source of truth.

Suggested content:

- job_version_id
- role_summary
- inferred role family
- normalized occupation
- seniority
- responsibility areas
- competencies
- languages
- education
- experience
- credentials/licenses
- schedule/availability
- work conditions
- employment/work arrangement
- remote eligibility
- hard requirements
- preferred requirements
- possible blockers
- real-work scenarios
- overall interpretation confidence
- provenance

Competency:

- canonical competency ID
- display name
- proficiency demand 1–5
- importance 1–3
- evidence
- confidence

Strict schema validation.

Malformed output gets bounded repair/retry, then degraded/failure state.

Never fabricate.

---

# 26. Demand / Fit Presentation

Avoid percentages.

Proficiency scale:

1. Familiar
2. Basic
3. Working
4. Strong
5. Advanced

Importance:

1. Supporting
2. Important
3. Core

Do not create nonsense bars for education/credentials.

Keep separate:

- Watch relevance
- Profile fit/readiness
- AI interpretation confidence

---

# 27. Real-Work Sanity Check and Professional Advice

Basic Free analysis may show 1–2 grounded scenarios.

Premium/deep may show 3–4.

Prompt framing:

> What this job may actually ask you to handle.

Response:

- Comfortable
- Could work through it
- Not yet

Responses never automatically change Profile.

Premium Professional Advice is on-demand and may use:

- JobDemandProfile
- relevant Profile
- sanity responses
- selected CV if needed

Advice should be specific, prioritized, honest, and include what **not** to study.

---

# 28. CVs and Prepare to Apply

Original Base CV remains private until deleted.

P0 upload types:

- PDF
- DOCX

Premium Base CV count is configurable, e.g. up to 3.

CV-assisted Profile extraction produces suggestions only.

### Tailored CV

Never modify Base CV.

Create job-specific draft/version.

Allow:

- edit
- save
- copy
- download DOCX/PDF
- explicit versions
- rename/duplicate/archive/delete

Autosave should not create version spam.

Truthfulness:

AI may rephrase/reorder/emphasize existing facts.

AI must never invent skill, credential, date, experience, achievement.

P0 layout: one excellent ATS-friendly template.

Arbitrary uploaded-layout preservation is future.

### Prepare to Apply

Premium/on-demand:

- tailored CV
- checklist
- cover letter
- short application message
- recruiter/hiring-manager message

Do not auto-generate for every job.

Every meaningful generated text has Copy.

---

# 29. Career Prep

Premium top-level section:

- Professional Advice
- Interview Prep
- Company Research
- Practice Scenarios

Company Research is explicit, not silently injected into job analysis.

Basic real-work picture remains core/free.

Past interview notes may be used on-demand for personalized Premium prep with least-data selection.

Cross-job pattern insights are calm and on-demand only.

Never create permanent performance scores.

---

# 30. Writing Policy and Future Personalization

No tone/style chooser in P0.

Default:

> Natural, professional, simple English. Preserve real voice and facts. Remove unnecessary AI-style wording. Adapt to role/document without asking for tone configuration.

Avoid:

- buzzwords
- clichés
- exaggerated enthusiasm
- robotic transitions
- inflated claims

User edits become working draft.

### Future Premium writing memory

Not a P0 dependency.

May learn only from explicitly accepted/edited/saved content.

Merely displayed AI output is not a preference signal.

Use a compact private writing profile; no full-history prompt; no embeddings initially; allow reset.

---

# 31. AI Orchestrator and Provider Routing

Business logic never calls provider APIs directly.

Capabilities:

- AI_FAST
- AI_STANDARD
- AI_DEEP_REASONING
- AI_DOCUMENT

Orchestrator handles:

- task
- data classification
- minimum context
- allowed providers
- model capability
- cost ceiling
- cache
- retry/fallback
- schema validation
- provenance
- metering

Do not expose provider/model choice to users.

Do not silently downgrade to an inadequate model.

## P0 public route

Three Gemini API credentials from **three separate Google Cloud projects**.

Use health-aware round robin for **public/sanitized public** workloads.

Example:

```text
A → B → C → A
```

If B is quota-limited/unhealthy, temporarily remove it from rotation and return it after cooldown/reset.

Public/raw JD must be minimized/sanitized where necessary before public AI processing. Remove unnecessary personal contact blocks.

## P0 private route

One OpenRouter key for private/sensitive user-data AI tasks.

Enforce privacy-safe provider/model restrictions and no-data-collection/ZDR-style routing where supported.

If no approved private route exists, fail safely.

**Never fall back private data to the public Gemini pool.**

Private examples:

- CV
- Profile
- interview notes
- application notes
- work-authorization data
- private Career Prep
- personal writing history

## Secrets

SSM SecureString:

```text
/prod/ai/gemini/public/project-a/api-key
/prod/ai/gemini/public/project-b/api-key
/prod/ai/gemini/public/project-c/api-key
/prod/ai/openrouter/private/api-key
```

No plaintext provider secrets in DB, frontend, Git, logs, or Terraform state.

---

# 32. AI Cost Strategy

Top-level P0 requirement:

- deterministic filtering before AI
- strip HTML/navigation/footer
- canonical JD analysis once
- shared cache
- content hashes
- structured JobDemandProfile reused downstream
- selected CV only
- relevant Profile slices only
- no unrelated history
- output caps
- cheap model when adequate
- deep reasoning only on demand
- versioned selective reanalysis
- no whole-corpus reprocessing after prompt changes

Track every AI operation:

- task
- provider
- model/capability
- input/output tokens
- latency
- estimated cost
- cache hit
- success/failure
- analysis version
- correlation ID

Never log private prompt bodies.

Provenance includes:

- schema_version
- analysis_pipeline_version
- prompt_version
- competency_catalog_version
- occupation_catalog_version
- capability/model profile
- generated_at
- job_version_id

---

# 33. Technical Stack

Primary AWS region: **ap-southeast-1 (Singapore)**.

### Frontend

- Next.js App Router
- TypeScript
- static export
- private S3 origin
- CloudFront
- OAC
- no Next.js runtime server P0

### API

- Python
- FastAPI
- Lambda `.zip` where practical
- API Gateway HTTP API
- lean dependencies

### Database

- exactly one Neon PostgreSQL
- SQLAlchemy
- Alembic
- standard PostgreSQL portability

### Async

- EventBridge Scheduler
- PostgreSQL outbox
- SQS
- Lambda lightweight workers
- Fargate Spot browser workers

### Other

- S3
- Cognito
- SSM Parameter Store
- ECR
- CloudWatch
- Terraform
- GitHub Actions + OIDC

Do not add App Runner, EKS, Redis, OpenSearch, always-on EC2, or NAT Gateway unless later justified.

---

# 34. Database Strategy

Exactly **one** Neon PostgreSQL database in P0.

No Jobs DB/Profile DB/Audit DB split.

Use module boundaries in code.

Portability rule:

- standard PostgreSQL
- SQLAlchemy
- Alembic
- no core Neon/Supabase/RDS proprietary dependency

Normal API/workers use Neon pooled endpoint.

Alembic, `pg_dump`/restore, controlled admin operations use direct endpoint.

TLS required.

Use conservative SQLAlchemy pool settings.

### Search

P0 uses PostgreSQL:

- B-tree indexes
- full-text search
- trigram/fuzzy matching

No OpenSearch P0.

No vector DB P0.

Future semantic matching may add pgvector or another search layer when measured need justifies it.

---

# 35. Monorepo and Contracts

Recommended structure:

```text
job-platform/
├── apps/
│   ├── web/
│   └── api/
├── python/
│   ├── core/
│   ├── workers/
│   │   ├── scraper/
│   │   ├── ai/
│   │   ├── notification/
│   │   └── documents/
│   └── adapters/
├── contracts/
│   ├── events/
│   └── generated/
├── infrastructure/
│   └── terraform/
├── migrations/
├── tests/
│   ├── fixtures/
│   ├── integration/
│   └── contract/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── runbooks/
│   └── security/
├── .github/workflows/
├── scripts/
├── projectSpecs.md
├── AGENTS.md
└── README.md
```

Monorepo must remain modular and extractable.

Tooling:

- pnpm workspaces
- uv
- pyproject.toml
- uv.lock
- Ruff

FastAPI OpenAPI is frontend/backend contract.

Generate TypeScript client/types.

HTTP starts `/api/v1`.

Async events carry:

```json
{
  "event_id": "evt_...",
  "event_type": "job.analysis.requested",
  "schema_version": 1,
  "occurred_at": "...",
  "correlation_id": "...",
  "payload": {}
}
```

Prefer backward-compatible additions.

---

# 36. Fargate Spot Strategy

Browser-heavy scraper workloads use Fargate Spot.

Normal idle:

```text
Spot = 0
On-Demand = 0
```

Queue work → launch workers → process multiple messages → exit.

Do not launch one task per SQS message.

Worker:

- long-poll
- receive one heavy browser message at a time
- reuse browser process
- fresh browser context per job/site
- visibility heartbeat
- bounded max lifetime/max jobs/idle
- stop accepting on Spot interruption
- ACK only after durable success

On-Demand fallback is architecturally possible but disabled until metrics justify it.

Queue examples:

- source-discovery
- lightweight-fetch
- browser-scrape FIFO where useful
- interactive-AI
- AI-analysis
- notification
- document-generation
- maintenance
- DLQs

---

# 37. S3 Management and Prefix Showcase

Use meaningful security/lifecycle boundaries.

Example:

```text
jobapp-web-prod
└── frontend/

jobapp-private-prod
├── users/{user_id}/cvs/originals/
├── users/{user_id}/exports/
└── generated/{user_id}/documents/

jobapp-backup-prod
├── postgres/daily/
├── postgres/weekly/
└── recovery-manifests/

jobapp-ops-prod
├── scraper/fixtures/
├── scraper/temporary/
├── imports/temporary/
└── diagnostics/sanitized/
```

Prefixes are organizational/policy tools, **not security boundaries by themselves**.

Security comes from:

- S3 Block Public Access
- IAM
- bucket policy
- encryption
- signed access
- separate buckets where warranted

Lifecycle examples:

- CV originals: until explicit delete
- exports: short expiry
- generated artifacts: short expiry
- DB daily: short retention
- DB weekly: somewhat longer
- scraper/import temporary: aggressive expiry

---

# 38. Private File Access

Owner-only short-lived signed URL.

Flow:

```text
user asks download
→ backend authenticates
→ verifies ownership
→ creates short-lived GET-only presigned URL
→ browser downloads directly from S3
```

Rules:

- no permanent public links
- a few minutes expiry
- safe filename/content-disposition
- knowing object key is not authorization
- Admin/Superadmin do not receive owner-style access in normal P0 paths

---

# 39. Upload Security

Every upload is hostile until safe:

```text
UPLOADING
→ QUARANTINED
→ validate size/type/structure
→ malware scan
→ CLEAN or REJECTED
→ only CLEAN goes to parser/AI
```

P0 allowlist: PDF/DOCX.

Validate real file type, not browser MIME alone.

Reject macro-enabled/unsupported formats.

Scanning implementation can initially be lightweight/open-source in isolated worker but must be replaceable.

---

# 40. Security and Privacy Boundaries

Data classes:

### PUBLIC
Public jobs/company/source metadata.

### INTERNAL
Operational metrics, source health, non-sensitive config, deployment data.

### PRIVATE USER DATA
Watches, applications, Profile, private pasted JDs, preferences.

### SENSITIVE PRIVATE DATA
CVs, interview notes, Career Prep history, tailored documents, work authorization, contact data.

### SECRET
DB credentials, AI keys, notification credentials, session/deployment secrets.

Classification drives:

- storage
- auth
- admin access
- logging
- retention
- AI routing
- backup/deletion

---

# 41. Multi-Tenant Isolation

P0 mandatory.

Never trust browser `user_id`.

Backend session resolves current user.

Every private fetch/mutation verifies ownership or explicit authorized role.

Applies to:

- Watches
- UserJob
- Profile
- CVs
- applications
- notes
- private JDs
- tailored docs
- reminders
- notification settings
- exports

Use UUID/ULID-style externally exposed IDs where appropriate.

Automated cross-tenant tests required.

PostgreSQL RLS may be evaluated P1 as defense-in-depth, not added merely for portfolio decoration.

---

# 42. Admin Privacy

Admins cannot browse private career content in P0.

Allowed operational metadata can include:

- user ID
- account status
- plan
- active Watch count
- run status
- notification channel type
- source failures
- correlation IDs

Not allowed:

- CV bodies
- Profile details
- interview notes
- application notes
- private pasted JDs
- Career Prep content
- tailored documents

Future support access, if ever added, must be user-consented, scoped, expiring, and audited.

---

# 43. Privacy & Data UI

`Settings → Privacy & Data`

Provide:

- plain-language privacy summary
- Privacy Policy
- Terms
- AI-data explanation
- admin-access explanation
- primary Singapore-centered infrastructure + external provider disclosure
- Export my data
- Delete career data
- Delete account

Do not force users to interpret legal text to understand basic privacy.

---

# 44. Logging and Error Model

Production logs are structured and minimized.

Allowed:

- request/correlation IDs
- internal user ID
- job/watch IDs
- provider/task
- status
- duration
- token counts
- sanitized error code

Never log:

- passwords
- API keys
- session/auth tokens
- signed URLs
- CV bodies
- Profile free text
- interview notes
- private JD bodies
- private AI prompt/response bodies
- sensitive headers

Shared error taxonomy examples:

- SOURCE_UNAVAILABLE
- SOURCE_UNSUPPORTED
- AI_TEMPORARILY_UNAVAILABLE
- AI_OUTPUT_INVALID
- NOTIFICATION_FAILED
- QUOTA_EXCEEDED
- RATE_LIMITED
- FILE_REJECTED
- AUTHORIZATION_DENIED
- INTERNAL_ERROR

Users get safe message, retryability, correlation ID.

Preserve partial success.

---

# 45. Browser Security / API Abuse Protection

P0 security headers include deliberate:

- CSP
- HSTS
- X-Content-Type-Options
- Referrer-Policy
- Permissions-Policy
- frame-ancestors

Use restrictive CSP, tested before enforcement.

P0 abuse layers:

```text
CloudFront/API Gateway throttling
→ FastAPI per-user/per-feature limits
→ quota checks
→ concurrency controls
→ idempotency
```

Different endpoints get different cost limits.

WAF remains P1/evidence-driven, not mandatory for architecture appearance.

---

# 46. Cost Guardrails

P0.

Distinguish:

- entitlement quota
- request rate limit
- concurrency limit
- idempotency
- platform cost guardrail
- kill switch

When user hits quota:

- pause only affected feature
- keep old results
- explain reset/upgrade
- do not silently downgrade model
- unrelated functions continue

`UsageEvent` can include:

- user
- feature
- operation
- provider
- model/capability
- tokens
- estimated cost
- compute duration
- cache hit
- success
- timestamp

Admin sees basic cost analytics.

AWS Budget/billing alerts also configured.

---

# 47. Operational Kill Switches

P0 lightweight controls, e.g.:

- job_discovery_enabled
- manual_runs_enabled
- ai_analysis_enabled
- telegram_enabled
- whatsapp_enabled
- document_generation_enabled
- new_signups_enabled
- source-specific enabled
- browser scraper enabled
- deep reasoning enabled

Store product/operational controls in PostgreSQL Admin config.

Audit changes.

Advanced rollout/cohort experimentation is later.

---

# 48. Configuration and Secrets

One source of truth per setting.

### SSM SecureString

- DB URLs
- AI keys
- Telegram/WhatsApp credentials

### Terraform + SSM

- region
- queue/bucket identifiers
- runtime infrastructure defaults

### PostgreSQL Admin config

- plan quotas
- cooldowns
- source concurrency
- source enabled state
- kill switches

### Code

Safe fallback defaults only.

Typed config and fail-fast production startup.

Use workload-specific DB/IAM roles where useful.

---

# 49. Backup and Recovery

P0:

- Neon short built-in recovery capability
- independent logical PostgreSQL backup
- compressed `pg_dump`
- direct Neon endpoint
- private encrypted S3
- short retention
- documented restore
- periodic restore test

Example configurable retention:

- daily around 7 days
- weekly a few weeks

No expensive multi-region standby P0.

Backups are disaster recovery only, not user archives.

Deleted private data may remain in encrypted backup until expiry, but is not available to normal app, AI, analytics, or user restore.

Restore process must reconcile deletion state before reopening service.

---

# 50. Retention and Deletion

Centralized retention policy, not scattered hard-coded expiry.

Examples:

- CV/Profile/app/notes: until explicit delete/account delete
- referenced JobVersion: retain while referenced
- active canonical JD: retain
- obsolete unreferenced JobVersion: configurable ~180 days
- run detail: ~90 days
- verbose CloudWatch: ~14–30 days
- temp imports/scrapes/exports: short
- backups: short configured lifecycle
- audit: longer protected retention

Explicit deletion takes precedence.

### Hard delete vs archive

Explicit private-data deletion means real removal from active production storage.

Do not use generic `deleted_at` as privacy deletion.

Archive is allowed where lifecycle/history is intentional:

- Watch
- Application
- public Job lifecycle

### Deletion cascade

Use hybrid:

- service-level deletion orchestration
- strong foreign keys
- narrow DB cascade for true owned children
- restrictive relationships around shared public data

Deleting User A must never delete shared data needed by User B.

---

# 51. Account Deletion and Export

Three user concepts:

1. Delete individual item
2. Delete all career data
3. Delete account & personal data

Account deletion:

```text
confirm
→ revoke sessions immediately
→ disable account
→ stop Watches/personal work
→ durable idempotent purge
→ remove private DB/S3/personalization/notification data
→ verify
→ final deleted state
```

Clear warning:

> Your account and active personal career data will be permanently deleted. You will not be able to restore or retrieve your CVs, Professional Profile, applications, interview notes, saved jobs, tailored documents, or other private career data later.

Also accurately disclose temporary encrypted backup retention.

Offer **Export my data first**, but do not require it.

### Export

Private ZIP, async, short-lived signed URL, auto-expiry.

Use:

- CSV for tables
- JSON for rich structures
- original user-owned CVs
- saved generated documents

Exclude:

- audit internals
- platform logs
- raw internal prompts
- secrets
- unrelated shared corpus

No account restore/import in P0.

Future import may create new records in a new account, never resurrect old identity/state.

---

# 52. Account Activity and Audit

User-facing Account Activity is small and security-focused:

- email verified
- password changed
- CV deleted
- export requested
- notification channel changed
- account deletion requested

Separate from technical logs.

Security/Admin Audit is append-only in normal behavior.

Fields:

- event ID
- timestamp
- actor
- actor role
- action
- target type/id
- result
- correlation ID
- sanitized change metadata
- security metadata where appropriate

Normal application:

- INSERT yes
- authorized READ yes
- UPDATE no
- DELETE no

No private career bodies in audit.

---

# 53. Terms, Privacy, Cross-Border Processing

P0:

- versioned Terms
- versioned Privacy Policy
- signup acceptance/acknowledgement
- store versions + timestamp
- material change notification

Optional marketing consent, if ever added, is separate.

Primary infrastructure is Singapore-centered.

Do **not** promise all processing stays in Singapore.

Disclose that approved AI/messaging providers may process minimum required data elsewhere.

---

# 54. Production vs Dev/Test Data

Strict P0 separation.

Never copy real production private data into:

- local development
- CI
- fixtures
- screenshots
- README
- portfolio demos
- Git

CI never connects to production Neon.

Use synthetic data and sanitized fixtures.

Provide deterministic synthetic demo dataset and easy bootstrap/reset workflow.

No LocalStack P0.

Local:

- Next.js
- FastAPI
- local PostgreSQL
- workers
- mocks
- fixture adapters

Real AWS integrations are tested selectively.

No permanent paid staging P0; future ephemeral staging is allowed.

---

# 55. CI/CD, Supply Chain, Deployments

Use GitHub Actions + AWS OIDC.

No long-lived AWS access keys in GitHub.

Separate app deploy and Terraform deploy roles.

P0 checks:

- formatting
- lint
- typecheck
- unit/domain tests
- tenant isolation/security tests
- adapter fixture tests
- contract tests
- frontend build
- backend package
- Terraform validate
- vulnerability/secret scans

Use lockfiles.

Pin important versions.

Avoid `latest`.

ECR image scanning.

Use trusted/pinned GitHub Actions.

### Deployment

Build once → test/scan → deploy same immutable artifact.

Record:

- release version
- Git SHA
- build timestamp

Keep previous known-good artifact for rollback.

Run smoke tests.

### DB migration

Use expand/contract.

No Lambda-startup migration.

Destructive schema changes require deliberate review.

---

# 56. Terraform and AWS Resource Management

Terraform is infrastructure source of truth.

Normal:

```text
edit → fmt/validate → PR → plan → review → apply
```

AWS Console is for inspection/troubleshooting.

Emergency console changes must be reconciled into Terraform.

Add lightweight drift check.

Remote state:

- private S3
- encryption
- versioning
- Block Public Access
- S3-native lockfile where suitable

Do not intentionally put plaintext secrets in state.

### Naming/tags

Standard names such as:

```text
jobapp-prod-api
jobapp-prod-web
jobapp-prod-browser-scrape
jobapp-prod-private-files
```

Default tags can include:

- Project
- Environment
- ManagedBy
- Component
- Workload
- DataClass
- CostCenter
- Repository

Never place PII/secrets/search terms/CV names/emails in tags.

---

# 57. Encryption

P0 encryption at rest/in transit.

- HTTPS/TLS
- S3 server-side encryption
- encrypted backups
- TLS to Neon
- SSM SecureString

Use simple managed encryption initially.

Customer-managed KMS only when concrete compliance/security need justifies cost/complexity.

Keep upgrade path open.

---

# 58. Observability and Internal SLOs

CloudWatch:

- structured technical logs
- metrics
- alarms

PostgreSQL:

- compact operational aggregates for Admin UI

Correlation IDs:

- request_id
- run_id
- watch_id
- source_fetch_id
- scrape_task_id
- job_id
- ai_operation_id
- notification_id

Alarms:

- DLQ growth
- circuit opened
- source failure spike
- excessive queue age
- API 5xx spike
- all workers failing
- broad notification failure
- stuck outbox
- abnormal AI spend

No OpenSearch/Grafana/Datadog P0 absent need.

Internal SLOs focus on user workflow:

- scheduled discovery starts in expected window
- stuck runs detected
- source health
- AI queue completion
- malformed analysis rate
- notification dispatch
- outbox age
- API health

No public SLA P0.

---

# 59. Product Analytics

P0 first-party privacy-minimized events only.

Examples:

- JOB_WATCH_CREATED
- JOB_WATCH_ACTIVATED
- MANUAL_RUN_STARTED
- JOB_ANALYSIS_VIEWED
- JOB_SAVED
- APPLICATION_MARKED_APPLIED
- CV_TAILORING_REQUESTED
- CAREER_PREP_STARTED

Never put CV text, keywords, notes, Profile details, interview answers, or private JD body into analytics.

No session replay P0.

---

# 60. Admin Dashboard

Sections:

- Overview
- Source Operations
- Failed Runs
- User Source Requests
- AI/Cost Analytics
- Queue/Worker Health
- Notification Health
- Users/Entitlements

Source view may include:

- demand count
- success/failure
- affected users/Watches
- last success/failure
- adapter version
- extraction success
- discovered jobs
- duplicate rate
- scrape time
- grouped failure signature
- circuit state

Controls:

- Retry now
- disable
- mark degraded
- pause/resume
- clear failure state
- safe test after deployment

No arbitrary Python/JS editing in Admin.

All sensitive actions audited.

---

# 61. Testing Strategy

Risk-based, not coverage-number-driven.

### Unit/domain

Prioritize:

- Watch filtering
- entitlements/quotas
- dedup
- posting age
- experience classification
- state transitions
- notification dedup
- cost guardrails
- retention/deletion logic

### Security

Mandatory cross-tenant tests:

- User B cannot read/update/delete/download A
- cannot obtain signed URL
- Admin cannot browse private career data
- revoked/expired session rejected

### Adapter

Sanitized HTML fixtures.

Normal CI does not repeatedly hit live sites.

### AI

Mocks in normal CI.

Validate:

- schema
- bounds
- hard constraints
- routing/privacy policy
- malformed output behavior

Do not assert exact prose.

Use separate small real-model evaluation suite.

### Integration

- API ↔ PostgreSQL
- outbox ↔ queue abstraction
- upload ↔ quarantine
- AI ↔ persistence
- notification ↔ adapter
- deletion ↔ S3/DB

### E2E

Small critical-path suite:

- signup → Watch → Run → Job → Analysis → Inbox
- CV upload → scan → Profile suggestions
- Job → Applied → Interviewing → Notes

---

# 62. Incident Response

P0 documented runbooks.

```text
docs/runbooks/
├── security-incident.md
├── credential-compromise.md
├── admin-account-compromise.md
├── suspected-data-exposure.md
├── database-recovery.md
├── queue-dlq-recovery.md
├── notification-provider-outage.md
└── source-adapter-incident.md
```

Lifecycle:

**Detect → Contain → Investigate → Recover → Review**

Capabilities:

- revoke sessions
- disable account
- rotate secrets
- use kill switch
- inspect append-only audit
- preserve evidence
- restore safe config
- post-incident note

No enterprise SOC P0.

---

# 63. Documentation / Portfolio

Documentation is part of P0.

```text
docs/
├── architecture/
│   ├── system-overview.md
│   ├── async-processing.md
│   ├── data-model.md
│   ├── ai-pipeline.md
│   ├── scraper-architecture.md
│   ├── security-boundaries.md
│   └── s3-data-layout.md
├── adr/
├── runbooks/
└── security/
```

Prefer text-source diagrams such as Mermaid.

README should explain:

- problem
- product
- architecture
- why technology choices
- local setup
- production deployment
- testing
- security
- cost tradeoffs
- intentional non-choices

Major decisions get ADRs, e.g.:

- modular monolith + async workers
- Neon before RDS
- Fargate Spot scraping
- shared canonical corpus
- provider-neutral AI
- transactional outbox
- PostgreSQL workflow state before Step Functions
- no OpenSearch P0
- no LocalStack P0
- no permanent staging P0

---

# 64. Future Semantic Matching

Preserve:

- raw user intent
- structured terms
- normalized occupation
- competencies
- canonical corpus
- future vector reference fields

Future likely:

```text
broad discovery
→ deterministic filtering
→ semantic ranking
→ hybrid result
```

Semantic engine can only rank discovered jobs.

User feedback `Relevant / Not relevant` may become private future ranking signals, but must not silently rewrite Watch config.

---

# 65. Explicit P0 Non-Goals

Do not implement without reclassification:

- auto-apply
- CAPTCHA bypass
- external job-site user credential import
- EKS/Kubernetes
- always-on EC2
- App Runner
- Redis
- OpenSearch
- vector DB
- semantic matching
- Step Functions
- multi-region backend
- permanent staging
- enterprise SSO
- passkeys
- public developer API
- session replay
- advanced A/B testing
- arbitrary CV layout preservation
- full multilingual UI
- public SLA
- advanced SOC/SIEM
- sophisticated billing
- whole-corpus reanalysis
- “unlimited” plans

---

# 66. Implementation Phases

## Phase 0 — Scaffolding

- monorepo
- pnpm/uv/Ruff
- FastAPI
- Next.js static app
- local PostgreSQL
- Alembic
- OpenAPI-generated TS client
- Terraform skeleton
- CI
- synthetic seed data
- README/ADR baseline

## Phase 1 — Identity and Security Core

- Cognito
- PKCE
- opaque sessions
- roles/plans/entitlements
- privileged MFA
- CSRF/CORS
- Account Activity
- audit
- tenant-isolation tests

## Phase 2 — Watch / Source / Discovery

- Watch lifecycle
- platform/source UI
- custom URLs/CSV
- adapter framework
- source policies
- initial dedicated + generic adapters
- scheduled runs
- Run now
- run history

## Phase 3 — Corpus / Async Reliability

- Job/JobVersion/UserJob
- dedup
- lifecycle
- fetch coalescing
- durable run state
- outbox
- SQS
- idempotency
- partial success

## Phase 4 — Public AI and Inbox

- JobDemandProfile
- sanitizer
- AI Orchestrator
- three-project Gemini pool
- health-aware round robin
- cache
- cost metering
- schema validation
- Job Inbox

## Phase 5 — Notifications and Applications

- Telegram
- WhatsApp
- one-channel preference
- digest
- application states
- reminders
- notes/interview experience

## Phase 6 — Private Files / Profile / CV

- private S3
- quarantine
- malware scan
- signed download
- Base CV
- Profile
- CV-assisted suggestions
- export/delete

## Phase 7 — Premium Private AI

- OpenRouter private route
- private routing guardrails
- Profile comparison
- tailored CV
- Prepare to Apply
- Career Prep
- professional advice

## Phase 8 — Operations / Hardening

- Admin dashboard
- circuits/kill switches
- alarms
- backup/restore test
- cost guardrails
- security headers
- full P0 tests
- rollback verification
- runbooks
- internal SLOs

---

# 67. P0 Acceptance Criteria

## Product

- User can signup/verify/login.
- User can create/activate Watch.
- Scheduled/manual run can discover jobs.
- Jobs normalize/deduplicate.
- Watch match stays deterministic.
- Matching JD gets structured analysis.
- New jobs appear in Inbox.
- Optional digest works.
- Application tracking works.
- Analyze a Job works.
- Core works without Profile/CV.

## Security

- Cross-user access blocked.
- Admin cannot browse private career content.
- Private files require owner-authorized signed URL.
- Uploads are quarantined/scanned.
- Admin MFA enforced.
- sessions revocable.
- CSP/security headers enabled.
- secrets absent from Git/frontend/logs.

## Privacy

- Privacy & Data page exists.
- Export works.
- individual deletion works.
- account deletion is durable/non-restorable.
- active deleted private data cannot be retrieved.
- backup disclosure accurate.
- production data absent from dev/CI.

## Reliability

- outbox works.
- retries are idempotent.
- DLQs configured.
- partial source failure preserves success.
- stuck work observable.
- migration process controlled.
- rollback proven.

## Cost

- AI operations metered.
- quotas enforced.
- duplicate AI avoided.
- cache/coalescing work.
- Fargate idles at zero.
- AWS budget alerts configured.
- concurrency bounded.

## Operations

- source health visible.
- pause/retry works.
- kill switches work.
- append-only audit works.
- DB backup created.
- restore procedure tested.
- runbooks present.

## Portfolio

- clear README.
- architecture/security diagrams.
- ADRs.
- synthetic demo.
- easy local bootstrap.
- CI green.
- Terraform represents deployed AWS infra.

---

# 68. Final Engineering Rules

1. Build the smallest **complete production system**, not the fewest lines of code.
2. Do not add technology for résumé decoration.
3. Keep idle cost low.
4. Prefer managed/serverless services when appropriate.
5. Keep PostgreSQL/domain logic portable.
6. Keep module boundaries even in one repo/database.
7. Treat every external input as untrusted.
8. Treat privacy as architecture.
9. Never trust client-side authorization.
10. Make expensive work idempotent and attributable.
11. Use deterministic logic before AI.
12. Send minimum required user data to AI.
13. Keep public and private AI routes separated.
14. In-app is source of truth; external notifications are convenience.
15. Degrade gracefully; preserve successful work.
16. User controls application state and personal profile changes.
17. AI may advise/rephrase but never fabricate.
18. Explicit deletion means real active-data removal.
19. Prefer backward-compatible schema/contract evolution.
20. Keep P0 scope frozen unless a new requirement materially changes product behavior, privacy, security, legal/ethical boundaries, or operating cost.
