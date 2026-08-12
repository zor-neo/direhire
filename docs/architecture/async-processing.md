# Async processing

```mermaid
sequenceDiagram
  participant Route as Route/service
  participant DB as PostgreSQL
  participant Pump as Outbox pump
  participant Q as SQS/DLQ
  participant W as Worker
  Route->>DB: BEGIN business state + versioned OutboxEvent COMMIT
  Pump->>DB: Read unpublished event
  Pump->>Q: Publish stable envelope
  Pump->>DB: Mark published or record safe error metadata
  Q->>W: At-least-once delivery
  W->>DB: Idempotent durable result
  W-->>Q: ACK only after durable success
```

Envelopes carry `event_id`, `event_type`, `schema_version`, `occurred_at`, `correlation_id`, and a minimal payload. Workers reject unsupported versions, return SQS partial-batch failures, and rely on durable idempotency keys. Queue redrive is five attempts; DLQ and queue-age alarms are Terraform-managed. Shared public fetches use a normalized adapter/URL key, a short lease, and a five-minute result cache without storing Watch intent.
