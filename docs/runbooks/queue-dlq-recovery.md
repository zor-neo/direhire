# Queue and DLQ recovery

1. Identify workload, event type/version, safe error code, correlation ID, age, and count. Do not inspect private payload bodies in dashboards.
2. Pause the producer/capability if failures are systemic. Fix the consumer or dependency and deploy an immutable artifact.
3. Redrive a small bounded sample through the original queue. Consumers are idempotent; verify durable state and costs before broader redrive.
4. Redrive remaining messages in bounded batches, watch age/failure/cost metrics, and stop on recurrence.
5. Never edit event payloads in place. Use a documented compatibility consumer or a deliberate migration tool for an old schema.
