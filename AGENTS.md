# AGENTS.md

> Guardrails for AI coding agents and human contributors.  
> `projectSpecs.md` is authoritative for **what** the product should be.  
> `AGENTS.md` is authoritative for **how** changes should be implemented.

---

# 1. Read Before You Change

Before any non-trivial change:

1. read `projectSpecs.md`;
2. identify whether the work is P0, P1, P2, or Future;
3. inspect relevant module boundaries, tests, contracts, ADRs, and runbooks;
4. make the smallest coherent change that satisfies the requirement;
5. update tests and documentation when behavior or architecture changes.

Do not silently expand P0.

If a request conflicts with `projectSpecs.md`, surface the conflict before changing:

- product behavior;
- privacy semantics;
- security boundaries;
- source-access ethics;
- AI data routing;
- major architecture;
- ongoing cost posture.

---

# 2. Protect the Core Product Intent

The core flow is:

```text
Sources
→ scheduled/manual discovery
→ normalize/deduplicate
→ deterministic Watch match
→ structured holistic JD analysis
→ Job Inbox
→ optional digest
→ user-controlled tracking
```

The product must work without a Professional Profile or CV.

Do not make optional Profile/CV/Premium features prerequisites for discovery.

**Job Watch intent is the strongest signal.**

AI Profile Fit may enrich or rank, but must never silently hide a role that explicitly matched the Watch.

---

# 3. Respect Scope Levels

Use:

- **P0** for required Production MVP;
- **P1** for early production improvements;
- **P2** for growth;
- **Future** for architectural provision only.

Do not implement Future features merely because they appear in the spec.

Examples that remain non-P0 unless explicitly reclassified:

- EKS/Kubernetes
- Step Functions
- OpenSearch
- Redis
- vector DB
- semantic matching
- permanent staging
- multi-region
- enterprise SSO
- passkeys
- public API
- session replay
- advanced A/B testing
- auto-apply
- sophisticated billing
- arbitrary CV design preservation
- WAF for appearance only

---

# 4. Technology Choices Are Deliberate

P0 baseline:

- Next.js App Router + TypeScript, static export
- S3 + CloudFront + OAC
- FastAPI on Lambda
- API Gateway HTTP API
- exactly one Neon PostgreSQL database
- SQLAlchemy + Alembic
- PostgreSQL transactional outbox
- SQS
- Lambda lightweight workers
- Fargate Spot browser workers
- Cognito
- SSM Parameter Store
- S3 private files/backups
- ECR
- CloudWatch
- Terraform
- GitHub Actions + OIDC
- pnpm
- uv
- Ruff

Do not swap a core technology casually.

Do not add a new datastore, cache, workflow engine, search engine, or cloud service without:

- explicit requirement; or
- measured scale/security/operational need.

---

# 5. One Database Means One Database

P0 uses exactly one Neon PostgreSQL database.

Do not create:

- Jobs DB
- Profiles DB
- Audit DB
- worker DB
- analytics DB

Use code/module boundaries instead.

Core domain logic must remain portable standard PostgreSQL.

Do not leak Neon-, Supabase-, or RDS-specific features into core business logic unless isolated behind a deliberate adapter.

---

# 6. Database Access Rules

Use SQLAlchemy and repository/service boundaries.

Do not scatter raw SQL through routes/workers.

Raw SQL is acceptable only when:

- justified;
- encapsulated;
- tested;
- documented if non-obvious.

Use Alembic for migrations.

Never run migrations during Lambda startup.

Use:

- pooled Neon endpoint for normal API/worker traffic;
- direct endpoint for Alembic;
- direct endpoint for `pg_dump`/restore;
- direct endpoint for controlled administration.

Require TLS.

Keep application-side pools conservative.

---

# 7. Safe Schema Evolution

Prefer expand/contract:

1. add new field/table;
2. deploy code compatible with old + new;
3. backfill/migrate;
4. verify;
5. remove obsolete schema in a later release.

Do not rename/drop a critical field in the same release that first changes consumers.

Destructive migrations require deliberate review.

Migration failure stops deployment.

---

# 8. Keep Modules Real

The monorepo must remain modular.

Typical domains:

- auth/users
- entitlements
- jobs
- job watches
- applications
- profiles
- CV/documents
- sources/adapters
- AI
- notifications
- operations
- audit
- analytics
- config

Avoid:

- giant `shared` modules;
- circular dependencies;
- routes containing business logic;
- workers mutating unrelated domains directly;
- scraper importing CV logic;
- notification importing source internals.

Prefer:

```text
route/worker
→ application service
→ domain logic
→ repository
```

Shared code should mostly be stable contracts, enums, schemas, and utilities.

---

# 9. API Contracts

HTTP starts at:

```text
/api/v1
```

FastAPI OpenAPI is source of truth.

Frontend TypeScript client/types are generated.

Do not manually edit generated API clients.

Prefer backward-compatible additions.

Do not create `v2` for minor additions.

---

# 10. Async Event Contracts

Important outbox/SQS events use explicit envelopes:

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

Requirements:

- stable `event_id`
- explicit `schema_version`
- contract tests
- backward-compatible evolution where possible
- tolerate producer/consumer deployment overlap

`JobDemandProfile` also has explicit schema/provenance versioning.

---

# 11. Transactional Outbox Is Mandatory

For important DB → SQS transitions, do not:

```text
write DB
then publish SQS
```

as two unrelated operations.

Use:

```text
BEGIN
  write business state
  insert OutboxEvent
COMMIT
```

Then publish from dispatcher.

Monitor unpublished/stuck events.

---

# 12. Assume At-Least-Once Delivery

Do not assume exactly-once queue processing.

Every expensive or externally visible async task must be idempotent.

Examples:

- source discovery
- JD fetch
- canonical job creation
- AI analysis
- notification digest
- document generation
- account deletion

Use durable keys/hashes.

A retry must not:

- charge AI unnecessarily twice;
- create duplicate canonical jobs;
- send duplicate digests;
- create duplicate documents;
- partially delete data incorrectly.

---

# 13. Preserve Partial Success

One failed source must not discard successful work.

Example:

```text
4 sources succeeded
1 failed
→ Completed with warnings
```

Do not collapse every run into success/failure only.

Users should see safe, concise warnings.

Admins can see technical detail through correlation IDs.

---

# 14. Source Access Ethics Are Hard Limits

Never implement:

- CAPTCHA bypass
- imported external browser cookies
- external account password collection
- stolen/private session use
- access-control circumvention
- hidden/private endpoint abuse
- stealth designed to defeat platform protection

Preferred source method:

```text
official/public API
→ public HTTP
→ browser rendering only if necessary
```

If a source becomes questionable, pause/disable rather than escalate.

“Technically possible” is not the same as “supported”.

---

# 15. Scraper Worker Rules

Browser-heavy work runs on Fargate Spot.

Do not launch one task per message.

Worker should:

- start;
- long-poll SQS;
- receive one heavy browser message at a time;
- process multiple jobs;
- exit after idle/max lifetime/max jobs.

Browser behavior:

- reuse browser process;
- fresh browser context per job/site;
- no cross-job cookies;
- no persisted user sessions;
- visibility heartbeat;
- bounded retries;
- stop accepting new work on Spot interruption;
- ACK only after durable success.

Per-source concurrency is conservative and configurable.

---

# 16. Do Not Hammer Sources in CI

Normal CI uses sanitized fixture HTML.

Live health checks, if any, are operational and conservative.

When parser behavior changes, add/update fixture tests.

---

# 17. AI Must Be Structured

`JobDemandProfile` is source of truth for JD interpretation.

Do not repeatedly prompt raw JD downstream when structured analysis exists.

AI output must pass schema validation.

Malformed output:

1. bounded repair/retry;
2. degraded/failure state if still invalid;
3. never fabricate missing values.

Do not parse arbitrary prose when a structured contract exists.

---

# 18. Business Logic Never Calls AI Providers Directly

Use the AI Orchestrator.

Business code requests:

- task;
- capability;
- data classification.

Example:

```text
task = JOB_ANALYSIS
capability = AI_STANDARD
data_class = PUBLIC_AI_SAFE
```

Provider/model routing belongs inside AI infrastructure/configuration.

Users do not choose model/provider.

---

# 19. P0 AI Routing Rules

## Public/sanitized public work

Use three Gemini API credentials from three separate Google Cloud projects.

Use health-aware round robin.

Track:

- health;
- cooldown;
- quota/rate-limit state;
- usage.

If one project is rate-limited, temporarily remove it from rotation.

## Private/sensitive work

Use the OpenRouter private route.

Enforce approved privacy-safe provider/model routing.

No-data-collection/ZDR-style constraints should be enforced where supported.

If no approved private route exists, fail gracefully.

**Never route private data to the public Gemini pool as fallback.**

---

# 20. Minimize AI Context

Before every AI request ask:

> What is the minimum data required?

Examples:

### JD analysis

Public/sanitized JD only.

### Profile comparison

JobDemandProfile + relevant Profile slice.

### CV tailoring

Selected Base CV + target job + relevant approved facts.

### Interview prep

Current job + relevant Profile/CV/history only.

Never send:

- all CVs;
- all applications;
- unrelated interview history;
- unrelated notes;
- other users’ data.

---

# 21. AI Privacy and Logging

Do not log private AI prompt/response bodies.

Record only operational metadata:

- operation ID
- task
- provider
- capability/model
- token counts
- latency
- cache hit
- estimated cost
- success/failure
- provenance
- correlation ID

Sanitize/minimize public/raw JD before public AI processing where necessary.

---

# 22. AI Must Remain Truthful

AI may:

- interpret
- summarize
- rephrase
- reorder
- emphasize
- recommend
- identify gaps

AI must not invent:

- skills
- credentials
- employment history
- dates
- project facts
- achievements
- work authorization
- salary
- employer facts

If uncertain, preserve uncertainty.

---

# 23. AI Cannot Silently Mutate Personal State

AI must never automatically:

- change Profile skills;
- set application status;
- create reminders;
- mark Applied;
- merge medium-confidence duplicates;
- rewrite Watch configuration;
- infer nationality;
- infer work authorization;
- overwrite user-edited writing.

AI may suggest.

The user controls meaningful personal-state changes.

---

# 24. Writing Style Is a Product Default

Do not add tone/model/reasoning controls unless scope is explicitly changed.

Default writing:

- natural
- professional
- simple English
- concise
- factual
- role-appropriate
- no inflated claims
- no generic AI clichés

If user edits generated text, preserve their edit as working draft.

---

# 25. Security: Never Trust Client Ownership

Do not authorize from browser-provided:

- `user_id`
- `owner_id`
- `role`
- `plan`

Resolve current user from server session.

Every private fetch/mutation must verify ownership or explicit role permission.

---

# 26. Cross-Tenant Security Tests Are Mandatory

For every private resource type, test:

- User A can access A;
- User B cannot read A;
- User B cannot update A;
- User B cannot delete A;
- User B cannot obtain signed URL for A;
- User B cannot enumerate A.

Also test:

- revoked/expired session rejected;
- Admin cannot browse private career content.

Do not consider a private resource complete without tenant-isolation tests.

---

# 27. Admin Privacy Boundary

Admin/Superadmin are operators, not default readers of private career data.

Do not add Admin views/endpoints for:

- CV body
- Profile details
- interview notes
- application notes
- private JD body
- Career Prep content
- tailored documents

Use operational metadata + correlation IDs.

Any future support-access feature requires a separately approved consent model.

---

# 28. Private S3 Access

Private S3 objects are never public.

Download:

```text
authenticate
→ verify ownership
→ create short-lived presigned GET URL
```

Rules:

- short expiry;
- no permanent public URLs;
- object key does not equal permission;
- safe content disposition;
- deleted object cannot receive new URL;
- Admin does not receive owner-style download access in normal P0 path.

---

# 29. Uploads Are Untrusted

Pipeline:

```text
QUARANTINED
→ validate size/type/structure
→ malware scan
→ CLEAN or REJECTED
```

Only CLEAN files can reach parser/AI.

P0 allowlist: PDF/DOCX.

Do not trust extension or browser MIME alone.

Reject macro-enabled/unsupported formats.

Never execute embedded content.

---

# 30. Logging Must Not Reproduce User Data

Allowed logging:

- IDs
- statuses
- duration
- provider
- token counts
- sanitized error codes

Never log:

- passwords
- API keys
- auth/session tokens
- signed URLs
- CV bodies
- Profile free text
- interview notes
- private JD text
- private AI prompt/response bodies
- sensitive HTTP headers

Do not add request/response body logging middleware in production.

---

# 31. Error Handling Is Centralized

Use typed/shared errors.

Do not expose:

- stack traces
- SQL errors
- raw Playwright exceptions
- provider payloads
- internal paths

Return:

- safe user message
- retryability
- correlation ID

Preserve partial successful work.

---

# 32. Data Classification Drives Implementation

Use:

- PUBLIC
- INTERNAL
- PRIVATE USER DATA
- SENSITIVE PRIVATE DATA
- SECRET

When adding a new entity/field, decide its class.

Then apply that classification to:

- authorization
- storage
- logs
- AI routing
- admin visibility
- retention
- backup
- deletion
- export

---

# 33. Explicit Deletion Means Real Active-Data Removal

Do not implement privacy deletion as only:

```text
deleted_at = now()
```

for private career content.

Hard-delete active private content when explicitly requested.

Archive/soft-delete is valid only where lifecycle/history is intentional, such as Watches or Applications.

---

# 34. Cascades Must Be Narrow and Safe

Use DB `ON DELETE CASCADE` only for unquestionably owned children.

Example:

```text
Application → InterviewNote
```

Do not cascade into shared canonical Jobs/JobVersions.

Deleting User A must never remove shared public data still needed by User B.

Add deletion integration tests.

---

# 35. Account Deletion Is a Durable Workflow

Do not try to delete an entire account synchronously in one HTTP request.

Flow:

1. confirm irreversible action;
2. revoke sessions;
3. disable account;
4. stop scheduled/personal work;
5. persist deletion workflow;
6. remove private DB data;
7. remove private S3 objects;
8. remove personalization/notification data;
9. verify;
10. finalize deleted state.

Workflow must be idempotent.

Deleted account is not restorable.

---

# 36. Export Rules

Exports:

- generated asynchronously;
- stored privately;
- short-lived;
- owner-authorized signed download;
- auto-expire.

Include meaningful user-owned data.

Exclude:

- secrets;
- audit internals;
- platform logs;
- raw internal prompts;
- other users;
- unrelated shared corpus.

No account restore from export in P0.

---

# 37. Production Data Never Becomes Dev/Test Data

Never copy production private data into:

- local DB
- CI
- fixtures
- screenshots
- demos
- README
- Git history

Use synthetic/sanitized data.

CI must not have production Neon credentials.

If production shape triggers a bug, reproduce with sanitized/minimized synthetic data.

---

# 38. Secrets Belong in SSM SecureString

Never commit or log secrets.

Do not place secrets in:

- frontend code
- source
- plaintext DB fields
- Terraform state intentionally
- test snapshots
- issue text
- build output

Use separate logical secrets for separate providers/workloads.

---

# 39. IAM Uses Least Privilege

Do not reuse broad admin-like roles for convenience.

Separate where useful:

- API runtime role
- scraper task role
- AI worker role
- notification role
- backup role
- app deploy role
- Terraform deploy role

Example principle:

A document worker should not read DB backups.

A backup job should not browse CV files.

---

# 40. Configuration Has One Source of Truth

Secrets → SSM SecureString.

Infrastructure/runtime → Terraform + SSM.

Product/operational controls → PostgreSQL/Admin.

Code → safe fallback defaults only.

Do not define the same setting independently in several places.

Config must be typed and validated.

Production fails fast on missing required config.

---

# 41. Cost Is a Correctness Requirement

Every expensive action must be attributable.

Before adding:

- AI call
- browser scrape
- Fargate runtime
- document generation
- messaging request

consider:

- cost
- retry
- idempotency
- caching
- quota
- concurrency
- observability

Avoid hidden unbounded loops.

Prefer idle-to-zero.

---

# 42. Do Not Silently Downgrade AI Quality

If a required capability is unavailable, do not silently use an inadequate model and claim success.

Use an explicitly approved equivalent route or fail gracefully.

---

# 43. Quotas Are Feature-Scoped

Hitting one quota must not:

- erase existing results;
- break unrelated features;
- silently lower model quality.

Distinguish:

- quota exhausted
- rate limited
- concurrency blocked
- platform disabled

Return clear UI state.

---

# 44. Respect Kill Switches

Before expensive/external operations, check relevant platform/source control.

Examples:

- job discovery disabled
- manual run disabled
- AI disabled
- source disabled
- browser scraping disabled
- Telegram/WhatsApp disabled

Do not bypass operational controls.

Sensitive config changes must be audited.

---

# 45. Observability Must Follow the Workflow

Carry correlation IDs through:

- request
- Watch run
- source fetch
- scrape task
- job
- AI operation
- notification

Emit useful metrics:

- queue age
- retries
- failure rates
- cache hits
- cost
- stuck work
- circuit state

Do not create logs containing user content just to improve troubleshooting.

---

# 46. CloudWatch Retention Is Finite

Do not leave verbose log groups at infinite retention.

Use deliberate project defaults, initially around 14–30 days where appropriate.

Audit/user-history retention is separate.

---

# 47. S3 Prefixes Are Not Security Boundaries

Use prefixes for lifecycle/organization.

Security comes from:

- Block Public Access
- IAM
- bucket policies
- encryption
- signed access
- separate buckets where warranted

Do not assume `private/` prefix makes an object private.

Add lifecycle rules for temporary files, exports, and backups.

---

# 48. Backup Must Be Restorable

P0 backup:

- logical PostgreSQL dump;
- direct DB endpoint;
- compressed;
- private encrypted S3;
- short retention.

Maintain restore runbook.

Periodically test restore.

Do not claim recovery capability merely because dump files exist.

Backup roles should not have general application access.

---

# 49. Browser Security Headers Are P0

Do not weaken CSP/security headers casually.

New external scripts/domains require review before allowlisting.

Avoid wildcard sources.

No secret/private data in static Next.js bundle.

---

# 50. Rate Limits Must Reflect Endpoint Cost

Do not apply one arbitrary global limit to all routes.

Protect expensive actions before expensive work starts.

Repeated equivalent action should return/reuse existing operation where appropriate.

WAF remains evidence-driven, not a résumé checkbox.

---

# 51. Accessibility Is Part of Done

New UI must remain:

- keyboard reachable;
- semantically labeled;
- focus-visible;
- responsive;
- screen-reader sensible;
- not color-only.

Tooltips must work on hover, focus/click, and touch.

Do not introduce desktop-only interaction assumptions.

---

# 52. UX Must Stay Simple

Do not add unnecessary:

- AI model controls
- tone selectors
- reasoner settings
- dense analytics
- productivity scores
- premium nagging
- unexplained percentages
- permanent negative performance metrics

Prefer progressive disclosure and good defaults.

---

# 53. Job Watch Semantics Must Stay Stable

- Target = broad
- Required = mandatory
- Exclude = filter

Experience is strategic, not a hard guillotine.

AI Profile Fit cannot veto a deterministic Watch match.

Do not change this casually.

---

# 54. Eligibility Signals Must Be Evidence-Based

Do not infer nationality/work rights from personal characteristics.

Use explicit:

- JD evidence
- user-provided Profile data

Absence of sponsorship language = Unclear.

Remote ≠ worldwide.

---

# 55. Salary Must Never Be Invented

If salary is not stated, represent unknown/not provided.

P0 salary is informational.

Do not turn it into a Watch filter without explicit scope change.

---

# 56. Deduplication Must Be Conservative

High-confidence duplicate → may auto-merge.

Medium-confidence → keep separate + warning.

Low-confidence → separate.

One user’s duplicate judgment must not silently change global corpus identity.

---

# 57. Job Closure Must Be Evidence-Based

Do not mark a job closed after one missing scrape.

Source failure is not closure evidence.

Use:

- Active
- Uncertain
- No longer listed

---

# 58. Notifications Follow Product Rules

In-app is source of truth.

External channel is optional.

User chooses one account-level channel in P0.

Do not silently fail over Telegram ↔ WhatsApp.

No external message for no-match runs by default.

One digest per Watch run, not one message per job.

---

# 59. Application State Is User-Owned

AI must not infer:

- Applied
- Interviewing
- Rejected
- Offer

User changes status.

Reminder creation is also user-controlled.

---

# 60. Risk-Based Testing Is Mandatory

A behavior change is incomplete without appropriate tests.

Prioritize:

- domain logic
- tenant isolation
- authorization
- deletion
- idempotency
- outbox
- adapter fixtures
- AI schema/routing
- contracts
- integration boundaries

Do not chase arbitrary coverage percentages.

---

# 61. Normal CI Must Not Spend AI Quota

Use mocked AI in routine PR checks.

Real-model evaluation is a separate, bounded process.

Do not make every PR call Gemini/OpenRouter.

---

# 62. Dependency Discipline

Use lockfiles.

Avoid dependencies when current stack/stdlib is enough.

Pin important versions.

Avoid `latest` tags.

Run vulnerability and secret scanning.

Prefer smaller runtime dependency sets.

---

# 63. GitHub Actions Discipline

Use trusted actions and pin appropriately.

AWS authentication uses OIDC.

Do not add long-lived AWS access keys when OIDC is available.

Do not import arbitrary third-party workflow actions without review.

---

# 64. Terraform Is the Infrastructure Source of Truth

Normal permanent AWS changes go through Terraform.

Console is for inspection/troubleshooting.

Emergency manual changes must be reconciled back into Terraform quickly.

Run:

- fmt
- validate
- plan
- review
- apply

Do not hide infrastructure creation inside application scripts.

---

# 65. Terraform State Is Sensitive

Use private encrypted remote S3 state with versioning and public access blocked.

Do not commit state.

Do not intentionally place plaintext application secrets in state.

---

# 66. AWS Tags Must Be Safe

Apply centralized tags.

Do not put:

- email
- user search terms
- CV names
- secrets
- private notes
- sensitive identifiers

into AWS resource tags.

---

# 67. Deployments Are Immutable

Build once.

Test/scan.

Deploy that exact artifact.

Record:

- release version
- Git SHA
- build timestamp

Keep previous known-good artifact.

Run smoke checks.

Rollback by redeploying known artifact, not rebuilding an old branch.

---

# 68. No Permanent Staging in P0

Baseline:

- local
- CI
- production

Do not create permanent paid staging without explicit reclassification.

Keep Terraform environment structure compatible with future ephemeral staging.

---

# 69. Documentation Is Part of the Change

Update docs in the same change when behavior materially affects:

- architecture
- security
- data flow
- storage
- source access
- deployment
- operations
- user-visible product semantics

Do not let diagrams/README drift from code.

---

# 70. ADRs for Material Decisions

Create/update an ADR when changing a meaningful architecture tradeoff.

ADR should capture:

- context
- decision
- alternatives
- rationale
- consequences
- future trigger to revisit

Do not create ADRs for trivial refactors.

---

# 71. Synthetic Demo Must Stay Synthetic

Demo/seed data is fictional and deterministic.

Never copy production material into:

- seeds
- screenshots
- docs
- tests

Keep local bootstrap easy.

If setup gets cumbersome, improve scripts/docs rather than requiring manual reconstruction.

---

# 72. Avoid Over-Engineering

Before adding infrastructure, ask:

1. Is there a current P0 user need?
2. Is there a current security/reliability requirement?
3. Is there measured scale/cost pressure?
4. Can the existing stack solve it cleanly?

If not, defer.

Examples:

- no Redis until needed
- no OpenSearch until PostgreSQL insufficient
- no Step Functions until workflow complexity warrants it
- no CMK until security/compliance need
- no EKS
- no multi-region

---

# 73. Do Not Under-Engineer Critical Boundaries

Cost restraint must **not** remove:

- tenant isolation
- auth/session security
- MFA for privileged roles
- deletion correctness
- upload quarantine
- AI privacy routing
- idempotency
- transactional outbox
- backup/restore
- append-only audit
- cost guardrails
- secret handling
- security tests

These are P0.

---

# 74. Change Review Checklist

Before declaring a task complete:

## Product

- Does core flow remain intact?
- Did this accidentally expand P0?
- Is UX still simple?
- Does core still work without Profile/CV?

## Security

- Is authorization server-side?
- Any new private data?
- Any new secret?
- Any log leak?
- Any new external input?
- Any cross-tenant risk?
- Does Admin privacy remain intact?

## Privacy

- What data class is this?
- Does AI receive only minimum data?
- Does deletion cover it?
- Does export cover/exclude it correctly?
- Does retention cover it?
- Can Admin see it?

## Reliability

- Is async work idempotent?
- Is DB→queue transition durable?
- Is partial success preserved?
- Are retries bounded?
- What happens on worker interruption?

## Cost

- Does this create AI/provider/compute spend?
- Is it metered?
- Is it bounded?
- Is there a quota?
- Can it cache/coalesce?
- Can it idle at zero?

## Operations

- Is there a useful metric?
- Is there a safe user-facing error?
- Does an external/expensive capability need a kill switch?
- Does Admin have enough operational visibility?

## Testing

- unit/domain?
- tenant/security?
- contract?
- integration?
- adapter fixture?
- AI routing/schema?
- deletion?
- idempotency?

## Documentation

- README?
- architecture doc?
- ADR?
- runbook?
- event/schema docs?

---

# 75. Definition of Done

A change is done only when:

- requested behavior works;
- scope is correct;
- authorization is correct;
- privacy classification is respected;
- tests pass;
- lint/type checks pass;
- migrations are safe;
- user errors are safe;
- logs are privacy-safe;
- expensive actions are metered and idempotent;
- docs are updated when necessary;
- no unrelated services were introduced;
- no production private data was used;
- no secrets were committed.

---

# 76. Default Decision Direction

When uncertain between:

- adding new service vs current stack;
- exposing setting vs sensible default;
- sending more user data vs less;
- retrying indefinitely vs bounded failure;
- auto-mutating user data vs user approval;
- hiding deterministic Watch match vs showing it;
- logging payload vs metadata;
- complex architecture vs simpler architecture;

prefer:

- current stack;
- sensible default;
- less data;
- bounded failure;
- explicit user control;
- showing the deterministic match;
- metadata;
- simpler architecture.

If uncertainty materially affects privacy, security, source legality/ethics, or ongoing cost, stop and raise the decision instead of inventing a new direction.
