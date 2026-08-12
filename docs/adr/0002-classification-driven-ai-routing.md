# ADR 0002: Classification-driven AI routing

## Context

DireHire analyzes public job descriptions and also offers optional workflows containing Profile, CV, notes, or pasted-job data. A fallback between these classes could violate privacy, while exposing model selection would complicate the product and weaken centrally enforced policy.

## Decision

Business services specify task, capability, and data classification. Public/sanitized work uses a health-aware round robin across three separately credentialed Gemini projects. Private/sensitive work uses only an approved OpenRouter route with provider allowlisting, fallback disabled, required parameters, data collection denied, and ZDR requested. Private work fails gracefully when that route is unavailable and never falls back to Gemini. Both paths require strict structured output, bounded repair, idempotency, metering, and payload-free logs.

## Alternatives

- One provider/credential: simpler but couples quotas and cannot enforce the required privacy split.
- User-selected models: rejected because it exposes implementation policy and invites unsafe routing.
- Public fallback for private work: rejected as a privacy boundary violation.

## Consequences and revisit trigger

Operations must maintain separate SSM credentials and route health. Some private tasks may be unavailable rather than degraded. Revisit only if an approved provider offers equivalent enforceable privacy and quality with a measured cost/reliability benefit.
