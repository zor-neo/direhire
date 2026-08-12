# Data model and classification

```mermaid
erDiagram
  USER ||--o{ JOB_WATCH : owns
  JOB_WATCH ||--o{ WATCH_SOURCE : selects
  JOB_WATCH ||--o{ JOB_WATCH_RUN : creates
  JOB_WATCH_RUN ||--o{ WATCH_MATCH : records
  JOB ||--o{ JOB_VERSION : versions
  JOB ||--o{ SOURCE_LISTING : found_at
  USER ||--o{ USER_JOB : inbox
  USER ||--o{ APPLICATION : tracks
  APPLICATION ||--o{ APPLICATION_NOTE : owns
  USER ||--o{ PRIVATE_FILE : owns
  USER ||--o| PROFESSIONAL_PROFILE : optionally_owns
  USER ||--o{ PRIVATE_AI_ARTIFACT : owns
```

Public canonical jobs and versions are shared; tenant-owned Inbox state, Watches, applications, notes, Profile, CVs, pasted JDs, artifacts, exports, and deletion workflows are private. Foreign-key cascades are limited to unquestionably owned children. User deletion never cascades into shared Jobs. Explicit private deletion hard-deletes active content and removes private objects; archive states are used only for intentional lifecycle history.
