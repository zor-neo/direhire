#!/usr/bin/env bash
set -euo pipefail

test -n "${DATABASE_URL_PARAMETER:-}" && test -n "${BACKUP_BUCKET:-}"
database_url="$(aws ssm get-parameter --name "$DATABASE_URL_PARAMETER" --with-decryption --query 'Parameter.Value' --output text)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
object_key="logical/direhire-${timestamp}.sql.gz"

pg_dump --dbname="$database_url" --format=plain --no-owner --no-privileges \
  | gzip -9 \
  | aws s3 cp - "s3://${BACKUP_BUCKET}/${object_key}" \
      --sse AES256 --content-type application/gzip --only-show-errors

unset database_url
echo "Logical backup uploaded: ${object_key}"
