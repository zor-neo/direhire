# Source adapter incident

1. Pause or disable the specific adapter and preserve successful sources in affected runs.
2. Check official access documentation, HTTP status/media type, fixture/parser drift, rate limits, circuit state, and correlation IDs.
3. Never add CAPTCHA bypass, cookies, credentials, hidden endpoints, aggressive concurrency, or stealth behavior to restore access.
4. Update sanitized fixtures and parser/contract tests. Resume conservatively after a separately approved live health check.
5. If access is no longer clearly public/supported, keep the adapter disabled and remove it from the source UI.
