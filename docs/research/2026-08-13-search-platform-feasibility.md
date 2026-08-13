# Search Platform Retrieval Feasibility — 2026-08-13

## Purpose

This spike tested normal unauthenticated retrieval for JobStreet Malaysia, JobsDB Thailand, and JobThai before freezing the `SearchAdapter` contract. No account, private cookie, CAPTCHA handling, access-control bypass, or production user data was used.

The in-app browser could not start because its required sandbox metadata was unavailable. Browser-only network behavior remains unverified. Direct HTTP, public page state, static client bundles, public robots policies, and current terms were inspected.

## Outcome

| Platform | Search response | Detail response | Authentication | Result |
|---|---|---|---|---|
| JobStreet | SSR HTML containing normalized Apollo `jobSearchV7` state; 30 results/page | SSR HTML containing Apollo `jobDetails` state | None for observed pages | `PAUSED` |
| JobsDB | Same SEEK SSR/Apollo architecture as JobStreet | Same SEEK SSR/Apollo architecture as JobStreet | None for observed pages | `PAUSED` |
| JobThai | SSR Next.js/Apollo state and unauthenticated GraphQL; 20 results/page | Public Next.js RSC response containing `JobPosting` JSON-LD | None for observed requests | `DIRECT_HTTP` |

## JobStreet and JobsDB

### Observed behavior

- `GET /jobs?keywords=software+engineer&where=...` returned `200` and redirected to a stable SEO path.
- Search HTML contained `window.SEEK_APOLLO_DATA` with `jobSearchV7`, pagination, stable job IDs, titles, summaries, organisations, locations, listing dates, salaries, and work arrangements.
- `GET /job/{id}` returned `200` with `jobDetails` in Apollo state.
- Static public JavaScript included the `JobSearchV7` query and configured same-origin `/graphql` access.
- No login, challenge, CAPTCHA, or private cookie was required in the small research sample.

### Operational decision

Do not implement automated production retrieval without written permission or an applicable documented API agreement.

Reasons:

- The wildcard robots group disallows `/graphql`, `/api/jobsearch/`, query crawling generally, and job-detail paths (with a narrower keyword allowance for search URLs).
- Current JobStreet terms prohibit data-mining, robots, screen scraping, and similar automated extraction without prior written consent.
- The technically available GraphQL/SSR data therefore does not establish production permission.

References:

- [JobStreet Singapore terms](https://sg.jobstreet.com/terms)
- [JobStreet Malaysia robots policy](https://my.jobstreet.com/robots.txt)
- [JobsDB Thailand robots policy](https://th.jobsdb.com/robots.txt)
- [SEEK integration request](https://talent.seek.com.au/partners/integration-request/)

The registry may retain these platforms as known `PAUSED` entries, but the normal Watch endpoint must not offer them.

## JobThai

### Observed behavior

- A public category search returned `200`, approximately 2.6 MB of SSR HTML, and `__NEXT_DATA__` Apollo state.
- `searchJobs` returned 20 structured results and a total count. Observed result fields included stable ID, title, company, province/district, work location, salary, tags, and update timestamp.
- The public client configured `https://api.jobthai.com/v1/graphql`.
- An unauthenticated `searchJobs` POST using `JobsSearchFilter` with a keyword returned `200` JSON without errors.
- A public detail page returned `200` and embedded a complete `JobPosting` JSON-LD object in Next.js RSC data.
- The wildcard robots group currently allows `/`. No CAPTCHA or access challenge appeared in the small research sample.
- The public jobseeker terms pages were checked for obvious English automation/scraping clauses; none were found by keyword. This is not a legal conclusion and should be rechecked periodically.

References:

- [JobThai robots policy](https://www.jobthai.com/robots.txt)
- [JobThai jobseeker terms](https://www.jobthai.com/en/terms-of-service-jobseeker)

### Operational decision

Implement JobThai first as a conservative `DIRECT_HTTP` adapter:

- concurrency `1`;
- configurable delay, initially at least 10 seconds between live source requests;
- bounded pages/results per run;
- shared-fetch coalescing and cache reuse;
- no account/session cookies;
- pause immediately on challenges, authentication requirements, or material policy changes;
- fixture-only CI using synthetic values shaped like the observed responses.

## Contract consequence

A search adapter cannot only build a URL. SEEK supports public GET search pages, while JobThai keyword search is naturally represented by a GraphQL POST. The contract should produce a transport-neutral request:

```text
SearchQuery
→ SearchRequest(method, url, headers, body)
→ content provider
→ adapter parser
```

Headers are fixed adapter metadata, never imported user browser headers. Request bodies contain normalized Watch search criteria only. The content provider remains responsible for timeouts, response-size limits, policy controls, retries, and browser-vs-direct execution.

## Revisit triggers

- SEEK grants documented API/integration permission.
- Any platform changes robots/terms, requires authentication, or adds a challenge.
- Fixture parsing fails because the public response contract changes.
- Request volume or operational cost makes the current approach unsuitable.

## USAJOBS addendum — 2026-08-13

USAJOBS is classified `DIRECT_HTTP_CONFIGURED`: its official Search API is explicitly intended
for job-board and application consumption and supplies current public announcements with full
fields, stable IDs, locations, agency names, qualifications, duties, requirements, eligibility,
dates, and canonical USAJOBS links.

Production requirements:

- request the free API key through the USAJOBS Developer portal;
- store the key and the matching registration email in separate SSM SecureStrings;
- send the email as `User-Agent` and the key as `Authorization-Key` only at request time;
- request only public announcements with bounded result counts and shared caching;
- clearly credit USAJOBS and link users to the original announcement;
- never log, persist in request contracts, or expose the API key to the frontend.

The platform remains hidden while `DIREHIRE_USAJOBS_ENABLED=false`. Enabling it is an explicit
deployment action after both SSM parameters exist. Normal CI uses only a synthetic response fixture.

References:

- [USAJOBS Search API](https://developer.usajobs.gov/api-reference/get-api-search)
- [USAJOBS authentication](https://developer.usajobs.gov/guides/authentication)
- [USAJOBS API access request and terms](https://developer.usajobs.gov/apirequest/)
- [USAJOBS rate limiting](https://developer.usajobs.gov/guides/rate-limiting)

## External-market catalog addendum — 2026-08-13

These sites are deliberate user-initiated handoffs, not DireHire ingestion adapters. DireHire
builds an ordinary public search URL from the Watch target role and first location, clearly tells
the user that they are leaving DireHire, and does not retrieve, proxy, normalize, or store the
external results.

| Market | External destination | Selection reason |
|---|---|---|
| Vietnam | VietnamWorks + TopCV | Two current, high-volume local recruitment platforms; external-only because automated access is restricted |
| Japan | Daijob | Active international/bilingual job search suited to the product's cross-border audience |
| Malaysia | JobStreet Malaysia | SEEK's active local employment marketplace |
| Philippines | JobStreet Philippines | SEEK's active local employment marketplace |
| Australia | SEEK Australia | Current leading general employment marketplace in Australia |
| New Zealand | SEEK New Zealand | Current leading general employment marketplace in New Zealand |
| South Korea | JobKorea | Major active Korean job board, also identified by Korean government guidance |
| Taiwan | 104 Job Bank | Major active Taiwanese job marketplace with current listings |

Public destinations were checked using normal HTTP navigation. A successful page response supports
external navigation only; it does not grant permission for automated extraction. If a destination
changes or becomes unavailable, update the catalog rather than escalating access behavior.
