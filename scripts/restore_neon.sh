#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 || "${RESTORE_CONFIRMATION:-}" != "RESTORE DIREHIRE" ]]; then
  echo "Usage: RESTORE_CONFIRMATION='RESTORE DIREHIRE' restore_neon.sh s3://bucket/key target-postgres-url" >&2
  exit 2
fi

backup_uri="$1"
target_url="$2"
aws s3 cp "$backup_uri" - --only-show-errors | gzip -dc | psql "$target_url" --set ON_ERROR_STOP=on
echo "Restore completed; run the verification checklist in docs/runbooks/backup-restore.md."
