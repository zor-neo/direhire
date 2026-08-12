# Initial internal SLOs

These are operating targets, not user promises. Revisit after measured production traffic.

- API health: 99.5% monthly availability; p95 non-AI API latency below 1 second.
- Outbox: 99% of events published within 2 minutes; investigate any item older than 5 minutes.
- Discovery: 95% of scheduled runs begin within 10 minutes; successful sources survive individual-source failure.
- AI: 95% of queued operations begin within 10 minutes when enabled and within quota; no silent quality downgrade.
- Queue: no DLQ message untriaged for more than one business day; queue-age alarms use workload-specific thresholds.
- Backup: daily object present within 26 hours; successful isolated restore drill before launch and periodically thereafter.
- Security/privacy: revoke compromised sessions immediately; disable affected external capability first; no private content in operational logs.
