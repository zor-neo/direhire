# Watch UX Revamp — Implementation Plan

## Goal

Transform the Watch creation experience from a technical adapter-selection form into a user-friendly job search setup, while fixing the critical Watch creation bug and adding AI-powered query expansion.

## Working Agreement

This plan and `task.md` are the active product-direction documents for the Watch UX revamp. `projectSpecs.md` and `AGENTS.md` remain useful architectural and safety guidance, but research spikes may use deliberately disposable code and may relax maintainability conventions while feasibility is still unknown.

The boundaries that remain non-negotiable are: no authentication/CAPTCHA bypass, no imported user sessions or job-site credentials, no access-control circumvention, no secret/private-data leakage, and no production adapter whose operational behavior has not been understood.

Public-source feasibility must be established through practical observation before an adapter is designed. Research may inspect public HTML, JSON-LD, hydration data, REST/XHR, GraphQL or persisted GraphQL queries, public feeds, sitemaps, and normal browser-rendered requests. A browser-visible endpoint is evaluated on authentication requirements, stability, rate behavior, data completeness, and operational cost; it is not assumed suitable merely because one request succeeds.

Research outcomes are classified as `DIRECT_HTTP`, `BROWSER`, `LIMITED`, `PAUSED`, or `RESEARCH_ONLY`. Only fixture-tested, operational platforms are selectable in the production Watch form.

## Scope Summary

| Phase | Description | Depends On |
|-------|-------------|------------|
| **1** | Fix Watch creation bug | — |
| **2** | Backend schema evolution (experience enum, search_expansion, platform registry, SearchAdapter contract) | Phase 1 |
| **R** | Practical retrieval research (JobStreet, JobsDB, JobThai) | Phase 2 schema foundation |
| **3** | Static alias map for deterministic synonym matching | Phase 2 |
| **4** | Asynchronous AI query expansion after Watch creation | Phase 2, 3 |
| **5** | First SearchAdapter implementations (SEEK Group, JobThai) | Phase R |
| **6** | Frontend UX revamp (logo cards, experience dropdown, auto-detect URLs, auto-name) | Phase 2, 5 |

---

## Phase 1 — Fix Watch Creation Bug

> [!CAUTION]
> **Blocker.** No Watch-related work matters until creation actually persists.

### Root Cause Investigation

The backend [service.py:create()](file:///e:/MyDev/direhire/apps/api/src/direhire/watches/service.py#L28-L34) commits to DB correctly. The break is in the HTTP layer between frontend and backend.

**Suspected causes (investigate in order):**

1. **CSRF token bootstrap failure** — [api.ts:loadCsrfToken()](file:///e:/MyDev/direhire/apps/web/app/lib/api.ts#L23-L42) fetches from `/auth/csrf-token`. If this fails silently (CORS, missing cookie), every POST is rejected with 403.
2. **Base URL mismatch** — `NEXT_PUBLIC_API_BASE_URL` in [.env.production](file:///e:/MyDev/direhire/apps/web/app/../../../apps/web/.env.production) may not match the actual API location.
3. **Synthetic dev-user header** — `NEXT_PUBLIC_DEV_USER_ID` absent → requests have no user context → 401.
4. **Session cookie** — `credentials: "include"` requires matching origin/SameSite policy.

### Steps

1. Run the stack locally (`docker compose up` + `npm run dev`)
2. Open browser DevTools → Network tab
3. Attempt to create a Watch
4. Inspect the actual HTTP request/response for `/api/v1/watches` POST
5. Check: status code, response body, request headers (CSRF, cookie, user header)
6. Fix the identified layer

### Files Likely Involved

- [api.ts](file:///e:/MyDev/direhire/apps/web/app/lib/api.ts) — CSRF/auth headers
- [.env.production](file:///e:/MyDev/direhire/apps/web/.env.production) — base URL config
- Potentially [main.py CORS config](file:///e:/MyDev/direhire/apps/api/src/direhire/main.py)

---

## Phase 2 — Backend Schema Evolution

### 2A. Experience Level Enum

Replace free-text `experience_target` with a validated enum.

#### [MODIFY] [schemas.py](file:///e:/MyDev/direhire/apps/api/src/direhire/watches/schemas.py)

Add enum class and change field type:

```python
class ExperienceLevel(StrEnum):
    ANY = "ANY"
    ENTRY = "ENTRY"
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    EXECUTIVE = "EXECUTIVE"
```

Change in `WatchCreate`:
```diff
-    experience_target: str | None = Field(default=None, max_length=64)
+    experience_level: ExperienceLevel = Field(default=ExperienceLevel.ANY)
```

Change in `WatchRead`:
```diff
-    experience_target: str | None
+    experience_level: str
```

#### [MODIFY] [models.py](file:///e:/MyDev/direhire/apps/api/src/direhire/models.py) (JobWatch class, ~L27-48)

```diff
-    experience_target: Mapped[str | None] = mapped_column(String(64))
+    experience_level: Mapped[str] = mapped_column(String(16), nullable=False, default="ANY")
```

#### [NEW] Migration `20260813_0019_watch_experience_expansion.py`

```python
# Expand/contract: add new column, backfill, then drop old
op.add_column("job_watches", sa.Column("experience_level", sa.String(16), nullable=False, server_default="ANY"))
op.execute("UPDATE job_watches SET experience_level = COALESCE(experience_target, 'ANY')")
op.drop_column("job_watches", "experience_target")
```

> [!WARNING]
> Production is currently at migration `20260812_0018`. Migration `20260813_0019` must use expand/contract: add and backfill `experience_level`, keep `experience_target` for deployment overlap, and remove the old column only in a later verified migration. Historical free text must be normalized to a valid enum value rather than copied blindly.

---

### 2B. Search Expansion Column

#### [MODIFY] [models.py](file:///e:/MyDev/direhire/apps/api/src/direhire/models.py) (JobWatch class)

Add after `experience_level`:

```python
search_expansion: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

This stores the AI-generated query expansion. `None` for legacy/unexpanded Watches.

Included in same migration `20260813_0019`:

```python
op.add_column("job_watches", sa.Column("search_expansion", sa.JSON, nullable=True))
```

---

### 2C. Search Platform Registry

A static in-code registry of supported search platforms and their metadata.

#### [NEW] `apps/api/src/direhire/sources/platforms.py`

```python
@dataclass(frozen=True, slots=True)
class SearchPlatform:
    key: str                    # "jobstreet", "jobsdb", "jobthai", etc.
    name: str                   # Display name
    adapter_key: str            # Which SearchAdapter handles this
    regions: tuple[str, ...]    # ISO 3166-1 alpha-2 country codes
    tier: str                   # "A" (API), "B" (JSON-LD), "C" (browser)
    search_capable: bool        # True = can search by keywords, False = needs URL
    availability: str           # AVAILABLE, UNAVAILABLE, or PAUSED
    logo_filename: str          # For frontend display

SEARCH_PLATFORMS: dict[str, SearchPlatform] = {
    "jobstreet": SearchPlatform(
        key="jobstreet", name="JobStreet", adapter_key="seek_graphql",
        regions=("MY", "SG", "TH", "ID", "PH", "HK"),
        tier="A", search_capable=True, logo_filename="jobstreet.svg",
    ),
    "jobsdb": SearchPlatform(
        key="jobsdb", name="JobsDB", adapter_key="seek_graphql",
        regions=("TH", "HK"),
        tier="A", search_capable=True, logo_filename="jobsdb.svg",
    ),
    "jobthai": SearchPlatform(
        key="jobthai", name="JobThai", adapter_key="jobthai",
        regions=("TH",),
        tier="A", search_capable=True, logo_filename="jobthai.svg",
    ),
    # Future additions: glassdoor, dice, wttj, blognone, eures, usajobs
}

# Per-platform location mapping (platform_key → user_location → platform_location_id)
# Initially static, later could use platform autocomplete APIs
LOCATION_MAPS: dict[str, dict[str, str]] = {
    "seek_graphql": {
        "cambodia": "3006", "phnom penh": "3006-1",
        "thailand": "3015", "bangkok": "3015-1",
        # ... populated during adapter research
    },
}
```

#### [NEW] API endpoint: `GET /api/v1/watches/platforms`

Returns available search platforms with region metadata. Frontend uses this to render logo cards and filter by user's location.

Only `AVAILABLE` platforms are returned to the normal Watch UI. Known but unimplemented or operationally paused platforms are excluded from user selection.

Platform sources persist a validated `platform_key` as well as the server-resolved `adapter_key`. This is required because multiple platforms, such as JobStreet and JobsDB, may share one adapter. The backend does not trust a client-selected adapter mapping.

#### [MODIFY] [watches/routes.py](file:///e:/MyDev/direhire/apps/api/src/direhire/watches/routes.py)

Add route (or separate `platforms/routes.py`):

```python
@router.get("/platforms", response_model=list[PlatformRead])
def list_platforms() -> list[dict]:
    return [asdict(p) for p in SEARCH_PLATFORMS.values()]
```

---

### 2D. SearchAdapter Contract

Extend the existing adapter contract to support keyword search.

#### [MODIFY] [contracts.py](file:///e:/MyDev/direhire/apps/api/src/direhire/sources/contracts.py)

Add alongside existing `SourceAdapter`:

```python
@dataclass(frozen=True, slots=True)
class SearchQuery:
    keywords: list[str]
    location: str | None
    experience_level: str | None  # "ENTRY", "MID", etc.
    posting_age_days: int | None

class SearchAdapter(Protocol):
    key: str
    capabilities: AdapterCapabilities

    def build_search_url(self, platform_key: str, query: SearchQuery) -> str:
        """Construct the platform-specific search URL/params from Watch criteria."""
        ...

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        """Parse the search results page/response."""
        ...

    def health_check(self, content: str) -> bool: ...
```

The key difference: `SearchAdapter.build_search_url()` translates Watch parameters into a platform-specific query. The existing `SourceAdapter` takes a pre-known URL.

#### [MODIFY] [discovery/service.py](file:///e:/MyDev/direhire/apps/api/src/direhire/discovery/service.py)

Update `_process_source()` to handle both adapter types:

```python
def _process_source(self, run, watch, source):
    adapter = self.adapters.get(source.adapter_key)
    if adapter is None:
        raise AppError("SOURCE_UNSUPPORTED", ...)
    
    if isinstance(adapter, SearchAdapter) and source.source_kind == "PLATFORM":
        # Build search URL from Watch parameters
        query = SearchQuery(
            keywords=watch.search_expansion.get("expanded_targets", watch.target_terms),
            location=watch.locations[0] if watch.locations else None,
            experience_level=watch.experience_level,
            posting_age_days=watch.posting_age_days,
        )
        source_url = adapter.build_search_url(source.platform_key, query)
    else:
        # Existing crawl behavior
        source_url = source.url
        adapter.validate_source(source_url)

    # Rest of discovery logic (fetch content, parse, match)...
```

---

## Phase R — Practical Retrieval Research

Before implementing a platform adapter, inspect its normal public website behavior in both direct HTTP and an ordinary browser session. Record:

- search and job-detail retrieval mechanisms;
- whether authentication, private cookies, generated access tokens, or challenges are required;
- query/pagination/location parameters and response variants;
- stable job identity, canonical URLs, dates, location, summary and full-JD availability;
- conservative retry/rate behavior, caching potential and browser requirement;
- sanitized fixtures and a final feasibility classification.

Do not automate a route that depends on login, CAPTCHA bypass, private credentials, or protection evasion. If an undocumented public endpoint is viable but fragile, classify it `RESEARCH_ONLY` or `LIMITED` rather than presenting it as production-ready.

## Phase 3 — Static Alias Map

Deterministic synonym expansion for matching. Zero AI cost.

Aliases must be narrow, reviewed mechanical equivalents. They may participate in deterministic Target/Required/Exclude evaluation. Broader AI-generated related terms do not participate in the final deterministic match.

#### [NEW] `apps/api/src/direhire/watches/aliases.py`

```python
"""Deterministic alias map for common tech/job terms.

Used at match time to expand Watch terms into known mechanical variants.
This catches literal mismatches like "PostgreSQL" vs "Postgres" without AI.
"""

ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "python": ("python3", "python 3"),
    "javascript": ("js", "ecmascript", "es6"),
    "typescript": ("ts",),
    "react": ("reactjs", "react.js"),
    "angular": ("angularjs", "angular.js"),
    "vue": ("vuejs", "vue.js"),
    "node": ("nodejs", "node.js"),
    "postgresql": ("postgres", "pgsql"),
    "mongodb": ("mongo",),
    "kubernetes": ("k8s",),
    "docker": ("containerization",),
    "machine learning": ("ml",),
    "artificial intelligence": ("ai",),
    "devops": ("dev ops", "dev-ops"),
    "backend": ("back-end", "back end", "server-side", "server side"),
    "frontend": ("front-end", "front end", "client-side", "client side"),
    "fullstack": ("full-stack", "full stack"),
    "it support": ("help desk", "helpdesk", "desktop support", "technical support"),
    "data analyst": ("data analysis",),
    "qa": ("quality assurance", "test engineer", "sdet"),
    "ux": ("user experience",),
    "ui": ("user interface",),
    # ... ~100-200 entries, community-curated over time
}

def expand_with_aliases(terms: list[str]) -> list[str]:
    """Expand a list of terms with known aliases. Returns deduplicated list."""
    expanded: list[str] = list(terms)
    seen = {t.casefold() for t in terms}
    for term in terms:
        key = term.casefold()
        # Forward: term → aliases
        if key in ALIAS_MAP:
            for alias in ALIAS_MAP[key]:
                if alias.casefold() not in seen:
                    expanded.append(alias)
                    seen.add(alias.casefold())
        # Reverse: if term IS an alias, add the canonical
        for canonical, aliases in ALIAS_MAP.items():
            if key in (a.casefold() for a in aliases) and canonical not in seen:
                expanded.append(canonical)
                seen.add(canonical)
    return expanded
```

#### [MODIFY] [matching.py](file:///e:/MyDev/direhire/apps/api/src/direhire/watches/matching.py)

Integrate alias expansion into matching:

```diff
+from direhire.watches.aliases import expand_with_aliases

 def deterministic_match(*, text, target_terms, required_terms, excluded_terms):
     haystack = " ".join(text.casefold().split())
-    target_hits = tuple(term for term in target_terms if term.casefold() in haystack)
-    missing_required = tuple(term for term in required_terms if term.casefold() not in haystack)
-    excluded_hits = tuple(term for term in excluded_terms if term.casefold() in haystack)
+    expanded_targets = expand_with_aliases(target_terms)
+    expanded_required = expand_with_aliases(required_terms)
+    expanded_excluded = expand_with_aliases(excluded_terms)
+    target_hits = tuple(t for t in expanded_targets if t.casefold() in haystack)
+    missing_required = tuple(t for t in expanded_required if t.casefold() not in haystack)
+    excluded_hits = tuple(t for t in expanded_excluded if t.casefold() in haystack)
```

#### Tests

- Existing matching tests must pass (aliases don't break literal matches)
- New test: "PostgreSQL" in Watch matches JD containing "Postgres"
- New test: "Backend" in Watch matches JD containing "server-side"
- New test: aliases don't cause false positives (alias of one term doesn't accidentally match unrelated content)

---

## Phase 4 — AI Query Expansion

One asynchronous AI operation after Watch creation or a meaningful criteria edit generates semantic search expansions. Watch creation commits immediately and remains useful if expansion is delayed or unavailable.

### 4A. Expansion Contract

#### [NEW] `apps/api/src/direhire/watches/expansion_contracts.py`

```python
from pydantic import BaseModel, Field

EXPANSION_SCHEMA_VERSION = 1
EXPANSION_PROMPT_VERSION = "query-expansion-v1"

class TermExpansion(BaseModel):
    original: str
    variants: list[str] = Field(max_length=15)

class QueryExpansionResult(BaseModel):
    target_expansions: list[TermExpansion] = Field(max_length=30)
    required_aliases: list[TermExpansion] = Field(max_length=30)
    excluded_expansions: list[TermExpansion] = Field(max_length=30)
    location_variants: list[str] = Field(max_length=10)
    experience_keywords: list[str] = Field(max_length=10)
    schema_version: int = EXPANSION_SCHEMA_VERSION
```

### 4B. Expansion Service

#### [NEW] `apps/api/src/direhire/watches/expansion_service.py`

```python
class WatchExpansionService:
    """AI-powered query expansion for Watch search terms.
    
    Uses the AI orchestrator with the minimum Watch criteria required.
    Requested through the transactional outbox after Watch persistence.
    """
    
    def expand(self, session, watch_data: WatchCreate) -> dict | None:
        # 1. Build minimal prompt with watch terms only (§20)
        # 2. Route: task=QUERY_EXPANSION, capability=AI_STANDARD.
        #    Treat raw Watch intent/location as private by default. A future
        #    sanitized-public route may be introduced only with an explicit classifier.
        # 3. Validate response against QueryExpansionResult schema (§17)
        # 4. One bounded repair attempt if invalid
        # 5. Return validated expansion dict, or None if AI unavailable
        # 6. AI failure does NOT block Watch creation — just means no expansion
```

Key design decisions:
- **AI failure is non-blocking.** The Watch is created without waiting for expansion. Matching falls back to literal + alias map.
- **Least-data private routing by default.** Send normalized criteria only; never send unrelated Profile/CV/application data.
- **One operation per meaningful criteria version.** Cosmetic edits such as renaming do not re-expand. Cache in `search_expansion`.
- **Idempotency key:** `query-expansion:{hash_of_terms}:{EXPANSION_SCHEMA_VERSION}:{EXPANSION_PROMPT_VERSION}`

### 4C. Integration into Watch Service

#### [MODIFY] [service.py](file:///e:/MyDev/direhire/apps/api/src/direhire/watches/service.py)

```diff
 def create(self, owner_id: str, data: WatchCreate) -> JobWatch:
     values = data.model_dump(exclude={"sources"})
     watch = JobWatch(owner_id=owner_id, **values)
     watch.sources = [self._source_model(s.model_dump()) for s in data.sources]
+    # Persist an idempotent query-expansion request in the same transaction.
+    self.outbox.add_query_expansion_requested(watch, data)
     self.session.add(watch)
     self.session.commit()
     return watch
```

Same for `replace()`.

### 4D. Integration into Discovery

#### [MODIFY] [discovery/service.py](file:///e:/MyDev/direhire/apps/api/src/direhire/discovery/service.py)

When building search queries for SearchAdapters, prefer expanded terms:

```python
# In _process_source, when building SearchQuery:
expansion = watch.search_expansion or {}
expanded_targets = expansion.get("target_expansions", [])
# Flatten: original terms + all variants
keywords = list(watch.target_terms)
for exp in expanded_targets:
    keywords.extend(exp.get("variants", []))
```

When matching discovered listings, `deterministic_match()` uses only user terms plus the reviewed static alias map (Phase 3). AI expansion broadens platform retrieval but never independently satisfies Required terms, triggers Exclude terms, or establishes the final Watch match.

---

## Phase 5 — First SearchAdapter Implementations

### 5A. SEEK Group Adapter (JobStreet + JobsDB)

#### [NEW] `apps/api/src/direhire/sources/adapters/seek_graphql.py`

Single adapter serving both JobStreet and JobsDB via their shared GraphQL endpoint.

```python
class SeekGraphQLAdapter:
    key = "seek_graphql"
    capabilities = AdapterCapabilities(
        pagination=True, keyword_search=True,
        location_search=True, browser_required=False,
        full_description=False,  # search results have summary; full JD needs follow-up
    )
    
    DOMAINS = {
        "jobstreet": "https://xapi.supercharge-srp.co/job-search/graphql",
        "jobsdb": "https://xapi.supercharge-srp.co/job-search/graphql",
    }
    
    def build_search_url(self, platform_key: str, query: SearchQuery) -> str:
        # Construct GraphQL query with:
        # - keywords from query.keywords (joined)
        # - locationId from LOCATION_MAPS lookup
        # - experience level filter
        # - posting age filter
        # Returns the full request URL + params
        ...
    
    def discover_jobs(self, content: str, source_url=None) -> list[DiscoveredJob]:
        # Parse GraphQL JSON response → list of DiscoveredJob
        data = json.loads(content)
        jobs = data.get("data", {}).get("jobSearch", {}).get("jobs", [])
        # Map each to DiscoveredJob...
        ...
```

> [!IMPORTANT]
> **Research required before implementation:** Inspect all public response paths, not only GraphQL. SEEK sites may return different HTML, hydration, REST/XHR, GraphQL, persisted-query, locale-specific, or challenge responses in direct HTTP and browser contexts. The adapter cannot be built from assumptions.

#### Fixture tests

- Capture real GraphQL response → sanitize → save as fixture
- Test parser against fixture
- No live API calls in CI (§16)

### 5B. JobThai Adapter

#### [NEW] `apps/api/src/direhire/sources/adapters/jobthai.py`

```python
class JobThaiAdapter:
    key = "jobthai"
    capabilities = AdapterCapabilities(
        pagination=True, keyword_search=True,
        location_search=True, browser_required=False,  # TBD after research
        full_description=False,
    )
    # Implementation after endpoint research
```

> [!IMPORTANT]
> Same research requirement: inspect JobThai's actual search mechanism (API endpoint vs HTML scraping vs JSON-LD) before building.

---

## Phase 6 — Frontend UX Revamp

### 6A. Watch Creation Form Redesign

#### [MODIFY] [watches/page.tsx](file:///e:/MyDev/direhire/apps/web/app/watches/page.tsx)

Complete rewrite of the Watch creation form. The new form has three sections:

**Section 1: What are you looking for? (always visible)**
```
- "What role?" → text input (maps to target_terms, auto-split by comma)
- "Where?" → text input (maps to locations)
- "Experience level" → dropdown (ANY/ENTRY/JUNIOR/MID/SENIOR/LEAD/EXECUTIVE)
- [▾ More options] → collapsed section with:
    - Required terms
    - Excluded terms
    - Work arrangement (checkboxes: On-site, Hybrid, Remote)
    - Employment type (checkboxes: Full-time, Part-time, etc.)
    - Posting age (dropdown: 3/7/14/30 days)
```

**Section 2: Where should we search? (always visible)**
```
- Logo cards for available search platforms
- Filtered by entered location (fetch from GET /api/v1/platforms)
- "Recommended for [location]:" section + "Also available:" section
- Checkbox on each card, max 3 selected
- Selected platforms shown as removable chips
```

**Section 3: Watch a specific company (collapsed by default)**
```
- [▾ Watch a specific company's career page]
    - URL input with auto-detection
    - Detected ATS shown as label (e.g. "✅ Stripe via Greenhouse")
    - [+ Add another URL] up to 3
    - Supported platforms listed
```

**Auto-generated Watch name:**
```
Derived from: "{role} · {location}" e.g. "IT Support · Cambodia"
Editable via inline rename on the Watch card, not a required field during creation.

The API accepts an omitted name and generates the authoritative default server-side. A later criteria edit does not overwrite a name the user explicitly edited.
```

**Button: "Create Watch"** (not "Save draft")

Success message: *"Watch created. Activate it when ready to start discovery."*

### 6B. Platform Card Component

#### [NEW] `apps/web/app/components/platform-cards.tsx`

Reusable component for search platform selection:

```tsx
interface PlatformCardProps {
  platform: { key: string; name: string; regions: string[]; logo_filename: string };
  selected: boolean;
  disabled: boolean;  // true when max 3 reached and this one isn't selected
  onToggle: (key: string) => void;
}
```

### 6C. Custom URL Auto-Detection

#### [NEW] `apps/web/app/lib/detect-adapter.ts`

```typescript
const PATTERNS: Record<string, RegExp> = {
  greenhouse: /boards\.greenhouse\.io\//,
  lever: /jobs\.lever\.co\//,
  ashby: /jobs\.ashby\.io\//,
  recruitee: /\.recruitee\.com\//,
  personio: /\.jobs\.personio\.de\//,
  pinpoint: /\.pinpointhq\.com\//,
  workable: /apply\.workable\.com\//,
};

export function detectAdapter(url: string): { key: string; label: string } | null {
  for (const [key, pattern] of Object.entries(PATTERNS)) {
    if (pattern.test(url)) return { key, label: key.charAt(0).toUpperCase() + key.slice(1) };
  }
  return null; // Unknown — will try generic_public
}
```

### 6D. Platform Logos

#### [NEW] `apps/web/public/logos/` directory

SVG logo files for each supported platform. These need to be sourced/created:
- `jobstreet.svg`
- `jobsdb.svg`
- `jobthai.svg`
- `glassdoor.svg` (future)
- Generic fallback icon for unsupported/unknown

> [!NOTE]
> Prefer permitted official assets. Otherwise use neutral text/initial cards and a generic job-board icon; do not create imitations of protected brand marks.

### 6E. Styles

#### [MODIFY] [styles.css](file:///e:/MyDev/direhire/apps/web/app/styles.css)

Add new component styles for:
- `.platform-grid` — responsive grid of logo cards
- `.platform-card` — individual card with checkbox state
- `.platform-card.selected` — selected state with accent border
- `.platform-card.disabled` — dimmed when max reached
- `.chip-row` — selected platforms as removable chips
- `.collapsible` — expand/collapse sections
- `.url-input-group` — URL field + auto-detect label + remove button
- `.auto-name` — subtle auto-generated name display

---

## Verification Plan

### Automated Tests

```bash
# Backend
uv run pytest tests/ -v

# Specific test areas:
# - Watch creation with new experience_level enum
# - Alias expansion in deterministic matching
# - AI expansion service (mocked provider)
# - SearchAdapter contract compliance
# - SEEK GraphQL adapter fixture parsing
# - Platform registry correctness
# - Custom URL auto-detection

# Frontend build
cd apps/web && npx next build

# Contract drift check
pnpm run check:contracts
```

### Manual Verification

1. **Watch creation bug**: Create a Watch → verify it appears in list → verify DB record exists
2. **Experience dropdown**: Select each level → verify stored and displayed correctly
3. **Platform selection**: Enter location → verify recommended platforms change → verify max 3 enforced
4. **Custom URL auto-detect**: Paste Greenhouse URL → verify "Detected: Greenhouse" label appears
5. **Alias matching**: Create Watch with "PostgreSQL" → run against JD with "Postgres" → verify match
6. **AI expansion**: Create Watch → verify `search_expansion` column populated → verify expanded terms used in search query construction
7. **Watch name auto-generation**: Leave name blank → verify auto-generated from role + location

---

## Decisions (Resolved)

| # | Question | Decision |
|---|----------|----------|
| 1 | **SEEK GraphQL research** | ✅ Do browser research first, before writing any adapter code |
| 2 | **MVP source limit** | 3 search platforms + 2 custom URLs = **5 total per Watch**. Enforce in backend schema. Custom URLs demoted to power-user escape hatch. |
| 3 | **Old ATS dropdown** | ✅ Remove immediately. Replaced by auto-detect in collapsed custom URL section. |
| 4 | **Platform logos** | Use permitted official assets or neutral text/initial cards with a generic icon; no generated brand imitations |
| 5 | **Phase ordering** | Parallel where possible — group non-dependent phases for speed |
| 6 | **Research posture** | Practical disposable probes are allowed; production adapters require a recorded feasibility result and sanitized fixtures |
| 7 | **AI match boundary** | AI expands retrieval only; final Watch matching remains deterministic using user terms and reviewed aliases |
| 8 | **AI routing/execution** | Asynchronous outbox workflow; least-data private routing by default; creation never waits for AI |
