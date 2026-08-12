# Private S3 layout

| Prefix | Data | Access/lifecycle |
| --- | --- | --- |
| `quarantine/{user}/{file}` | Untrusted PDF/DOCX upload | Owner workflow and scanner only; never downloadable as clean content. |
| `clean/{user}/{file}` | Validated CV/document | Owner-authorized short-lived signed GET only. |
| `documents/{user}/…` | Generated ATS DOCX/PDF | Document worker writes; owner downloads. |
| `exports/{user}/…` | Private export ZIP | Expires after two days. |
| `temporary/…` | Intermediate artifacts | Expires after two days; incomplete multipart uploads abort. |
| backup bucket `logical/…` | Compressed PostgreSQL dumps | Separate backup role and bucket; 14-day current retention. |

Prefixes organize lifecycle but are not authorization boundaries. Block Public Access, IAM, bucket policies, encryption, ownership checks, and signed requests provide security. Object keys never grant permission.
