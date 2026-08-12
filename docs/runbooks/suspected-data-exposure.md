# Suspected data exposure

1. Stop the implicated endpoint, private AI route, signed-download path, or external channel using an audited control.
2. Identify data classification, owners, object/operation IDs, access timestamps, and recipient boundary without reproducing the content.
3. Revoke sessions, delete or quarantine exposed temporary artifacts, and rotate signed access by denying new URL creation. Existing short-lived URLs expire naturally; tighten policy if required.
4. Verify tenant filters, Admin privacy behavior, logs, export/deletion behavior, and S3/IAM policies with focused tests.
5. Apply the incident communication and legal assessment appropriate to confirmed scope, then document prevention work.
