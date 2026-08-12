# ADR 0003: Public-feed-first launch sources

## Context

P0 needs useful job discovery without violating source terms, collecting external credentials, or funding an always-on browser fleet. Current official documentation exposes public employer-controlled feeds for several common ATS products.

## Decision

Launch with strict dedicated adapters for Greenhouse, Lever, Ashby, Recruitee, Personio, and Pinpoint plus a schema.org generic public adapter. Validate documented hosts/paths and required response modes. Routine CI uses sanitized fixtures only. API-key-only platforms such as SmartRecruiters and Teamtailor, login-only boards, and undocumented endpoints are excluded. Browser compute is provisioned as an idle-to-zero Fargate boundary but no launch adapter requires it.

## Alternatives

- Major-board scraping: rejected because access is less stable and often ethically or contractually questionable.
- Arbitrary careers-page crawling: rejected because P0 does not promise autonomous site discovery.
- Credentialed ATS integrations: deferred because they add secret onboarding and support cost without a launch requirement.

## Consequences and revisit trigger

Coverage favors employers with public ATS feeds and may miss some SEA boards. Revisit an adapter only after current official-access research, measured user value, fixture coverage, rate/concurrency policy, and an operational disable path.
