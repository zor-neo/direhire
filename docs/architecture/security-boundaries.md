# Security boundaries

- Cognito Authorization Code + PKCE verifies issuer, audience, signature, nonce, token use, and verified email. The API issues opaque hashed sessions with secure cookies, CSRF, expiry, revocation, and security-version invalidation. Privileged roles require MFA.
- Every private query resolves the current server session and filters by owner. Cross-tenant tests cover reads, mutations, deletion, enumeration, and signed URLs. Superadmin endpoints expose operational metadata, never career bodies.
- Uploads enter `QUARANTINED`, are size/type/structure checked and scanned by ClamAV, then become `CLEAN` or `REJECTED`. Only CLEAN PDF/DOCX objects can be read or sent to AI.
- Public fetches reject credentials, non-public IPs, private DNS resolutions, nonstandard ports, redirects, oversized bodies, and unsupported media. Dedicated adapters additionally validate documented hosts and paths.
- Terraform blocks all S3 public access, separates runtime roles, constrains SSM paths, uses OIDC deployment, enables finite logs and budgets, and requires immutable image digests.
- Logs and errors contain identifiers, statuses, safe codes, timing, and correlation IDs only. Request/response body logging is not installed.
