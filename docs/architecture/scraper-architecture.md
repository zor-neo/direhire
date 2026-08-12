# Browser worker architecture

P0 launch sources use documented public JSON/XML/RSS endpoints and do not need browser rendering. Terraform nevertheless defines a Fargate-compatible browser image/task boundary so a future reviewed adapter can use it without moving browser code into Lambda.

No ECS service or desired count exists, so browser compute idles at zero. Before enabling a browser adapter, add an explicit versioned browser event, a queue-triggered coalescing launcher (never one task per message), long polling, one message at a time, browser-process reuse, a fresh context per job/site, visibility heartbeats, Spot interruption draining, bounded job/lifetime/idle limits, and ACK only after durable success. Source policy must explicitly allow browser access. CAPTCHA bypass, user cookies, login credentials, private endpoints, and stealth circumvention remain prohibited.
