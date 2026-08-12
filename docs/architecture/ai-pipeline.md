# AI pipeline

```mermaid
flowchart TD
  Request --> Class{Data class}
  Class -->|PUBLIC_AI_SAFE| Sanitize[Sanitize public JD]
  Sanitize --> Gemini[Health-aware round robin: 3 Gemini projects]
  Class -->|PRIVATE / SENSITIVE| Minimize[Immutable minimum-data snapshot]
  Minimize --> OpenRouter[Approved provider only; ZDR/data collection denied]
  Gemini --> Validate[Strict versioned schema validation]
  OpenRouter --> Validate
  Validate -->|invalid| Repair[One bounded repair]
  Repair --> Result[Durable success or explicit degraded/failure]
  Validate --> Result
```

Business services request a task, capability, and classification; provider selection stays in the orchestrators. Private data never falls back to the public pool. Operations store provider/model provenance, token counts, latency, cache state, estimated cost, result, and correlation ID—never private prompts or response bodies. `JobDemandProfile` is the reusable structured interpretation of a JD. AI may suggest personal-state changes but cannot silently apply them or invent facts.
