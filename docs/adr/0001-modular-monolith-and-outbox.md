# ADR 0001: Modular monolith with transactional outbox

Status: Accepted  
Date: 2026-08-11

## Context

P0 needs strong domain boundaries and reliable asynchronous work while keeping idle cost and operational complexity low. A synchronous database write followed by an unrelated queue publish can lose work.

## Decision

Use one FastAPI modular monolith and one portable PostgreSQL database. Keep route → service → domain → repository boundaries. Persist important workflow state and a versioned outbox event in the same transaction; a separate dispatcher will publish to SQS. Consumers must remain idempotent because delivery is at least once.

## Alternatives

- Microservices and multiple databases: rejected for P0 cost and operational burden.
- AWS Step Functions: deferred until measured workflow complexity justifies it.
- Direct publish after commit: rejected because it cannot make DB state and queue intent atomic.

## Consequences

Modules remain extractable, but deployment starts simple. The dispatcher and stuck-event monitoring are required before production discovery is enabled. Outbox rows add modest storage and cleanup work.

## Revisit trigger

Revisit orchestration only when measured workflow complexity, throughput, or operational failure modes exceed what PostgreSQL state plus SQS can handle cleanly.

