# Authentication and session boundary

DireHire uses Cognito User Pools with Authorization Code + PKCE. The browser starts at `/api/v1/auth/login`; the backend generates state, nonce, and the PKCE verifier. Those short-lived values are kept in HttpOnly, SameSite=Lax cookies scoped to the authentication routes. The authorization code is exchanged server-side.

The ID token is accepted only after RS256 signature verification against the user pool JWKS plus issuer, audience, expiry, token-use, nonce, subject, and verified-email checks. Cognito access, ID, and refresh tokens are not persisted in browser storage or the application database.

After validation, the backend creates a random opaque session token. Only its SHA-256 hash and operational metadata are stored in PostgreSQL. The raw token is sent in a Secure, HttpOnly, SameSite=Lax cookie in production. A separate readable CSRF cookie must match the request header and the session's stored CSRF hash for mutations.

Sessions fail closed when expired, revoked, attached to a disabled account, or issued for an older user security version. `last_seen_at` is updated at a bounded interval. Admin and Superadmin sessions are rejected unless the account has confirmed MFA.

The `X-DireHire-User-ID` mechanism is a local-only development seam. It requires an explicit setting and production configuration validation forbids it.

No authentication token, authorization code, PKCE verifier, signed URL, or private payload may be logged.
