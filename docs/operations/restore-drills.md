# Restore drill record

## 2026-08-12 — local synthetic PostgreSQL 17.6

- Scope: disposable databases `direhire_backup_drill_source_20260812` and `direhire_backup_drill_target_20260812` in the pinned Compose PostgreSQL container.
- Data: deterministic fictional seed only; no production data or credentials.
- Procedure: upgraded source from base through Alembic `20260812_0018`, seeded one fictional user/Watch, streamed `pg_dump --format=plain --no-owner --no-privileges` through gzip/decompression into `psql --set ON_ERROR_STOP=on` on the target.
- Verification: target revision `20260812_0018`; one user; one Watch; eight platform controls. Pipeline exited successfully.
- Cleanup: both explicitly named disposable databases were dropped and a follow-up query returned zero matching drill databases. The regular `direhire` database and persistent volume were not changed.
- Production follow-up: after the first AWS backup object is created, repeat the S3 retrieval/encryption/age checks and record its safe object key, release SHA, task result, duration, and recovery result without inspecting private content.
