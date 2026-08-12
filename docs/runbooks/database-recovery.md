# Database recovery

Use [backup-restore.md](backup-restore.md) for the controlled procedure. Freeze application writes or disable affected workflows, select the last verified logical backup and known-good application release, and restore only to an isolated database first. Validate Alembic revision, referential integrity, key workflow counts, tenant ownership, and outbox state before any production cutover. Never use production data in local/CI or browse private bodies during recovery. Reconcile connection parameters through SSM and record recovery point/time achieved.
