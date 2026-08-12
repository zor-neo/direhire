# Notification provider outage

In-app notifications remain authoritative. Disable only the affected Telegram or WhatsApp control; do not silently fail over channels. Confirm deliveries retain a retryable safe error and existing digests remain visible. After provider recovery, re-enable the same channel and retry idempotently so a digest is not sent twice. Communicate that external delivery is delayed without exposing destination values beyond the existing mask.
