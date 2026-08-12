# Logical backup and restore

Production creates one compressed logical PostgreSQL dump each day from Neon's direct endpoint. The backup task can read only the direct database URL parameter and write only `logical/` objects in the encrypted backup bucket. S3 lifecycle expires current objects after 14 days and non-current versions after 7 days.

## Verify a backup

1. Confirm the ECS task exited successfully and emitted only the S3 object key, never the connection URL.
2. Confirm the new object is non-empty, encrypted, and within the expected age window.
3. Confirm the CloudWatch backup log group has 30-day retention.

## Restore drill

Use an empty, isolated PostgreSQL database created for the drill. Never restore over production and never copy production private data into local development or CI.

1. Obtain a short-lived operator session with read access to the selected backup object.
2. Set `RESTORE_CONFIRMATION='RESTORE DIREHIRE'` and run `scripts/restore_neon.sh <s3-uri> <isolated-direct-url>` from the approved operations environment.
3. Run `alembic current`, verify the expected table count, and run read-only checks for referential integrity and row counts.
4. Verify a synthetic owner can authenticate against a separately sanitized test setup. Do not inspect production career bodies during the drill.
5. Destroy the isolated drill database under the approved retention process and record the date, backup key, release SHA, result, duration, and operator in the audit record.

A dump is not considered recoverable until this drill succeeds. Run it before launch and periodically thereafter.
