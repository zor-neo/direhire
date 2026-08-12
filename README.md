# DireHire

DireHire is a production-oriented, low-cost job-search platform. Its P0 workflow is public-source discovery → normalization/deduplication → deterministic Watch matching → structured job analysis → Job Inbox → optional digest → user-controlled application tracking. A Professional Profile and CV are optional and never required for discovery.

## What is implemented

- Next.js App Router/TypeScript static application with accessible routes for Watches, Inbox, Analyze a Job, applications, optional career tools, schedules/notifications, Privacy & Data, and privacy-safe Superadmin operations.
- FastAPI `/api/v1` modular monolith with generated OpenAPI/TypeScript contracts, Cognito Authorization Code + PKCE, opaque revocable sessions, CSRF, privileged MFA, tenant ownership, entitlements, and append-only audit.
- One SQLAlchemy/Alembic PostgreSQL data model with transactional outbox, versioned events, partial-success discovery, conservative deduplication, coalesced public fetches, SQS partial-batch workers, stuck-work visibility, and audited kill switches.
- Six documented public launch adapters (Greenhouse, Lever, Ashby, Recruitee, Personio, Pinpoint), a schema.org generic adapter, and fixture-only normal CI.
- Structured public Gemini routing across three projects and private OpenRouter-only routing with minimum-data snapshots, ZDR/data-collection restrictions, quotas, idempotency, metering, and no public fallback.
- Quarantined PDF/DOCX upload, structural validation, ClamAV scanning, private S3 ownership checks, optional Profile/Base CV, ATS DOCX/PDF generation, export, career-data deletion, and durable irreversible account deletion.
- Terraform for S3/CloudFront/OAC, API Gateway/Lambda, Cognito, SQS/DLQs, finite CloudWatch retention, ECR, idle-to-zero Fargate task definitions, daily logical backups, IAM separation, and AWS budgets. GitHub Actions use OIDC and immutable digest-pinned releases.

## Local setup

Prerequisites: Python 3.12+, uv, Node.js 22+, Corepack, Docker, and Terraform.

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
python -m uv sync --frozen
python -m uv run alembic upgrade head
python -m uv run python scripts/seed_synthetic.py
corepack pnpm install --frozen-lockfile
python -m uv run uvicorn direhire.main:app --app-dir apps/api/src --reload
corepack pnpm dev
```

Local development may set `DIREHIRE_ALLOW_INSECURE_DEV_AUTH=true` and `NEXT_PUBLIC_DEV_USER_ID` to use the deterministic fictional account. Production rejects this mode. Routine tests never contact live job sources or AI providers and never use production data.

## Verification

```powershell
python -m uv run ruff format --check .
python -m uv run ruff check .
python -m uv run pytest
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm build
corepack pnpm audit --prod
terraform -chdir=infrastructure/terraform fmt -check -recursive
terraform -chdir=infrastructure/terraform validate
```

After changing HTTP routes or schemas, run `corepack pnpm generate:openapi` and `corepack pnpm generate:types`; generated clients are never edited manually. `tasktracker.md` records verification and handoff state. `projectSpecs.md` defines product behavior and `AGENTS.md` defines engineering guardrails.

## Documentation

- [System architecture](docs/architecture/system-overview.md)
- [Security boundaries](docs/architecture/security-boundaries.md)
- [AI pipeline](docs/architecture/ai-pipeline.md)
- [Source adapter policy](docs/architecture/source-adapters.md)
- [Deployment and rollback](docs/runbooks/deployment-rollback.md)
- [Backup and restore](docs/runbooks/backup-restore.md)
- [Authentication](docs/security/authentication.md)
