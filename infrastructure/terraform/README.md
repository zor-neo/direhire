# Production Terraform

This directory represents the permanent P0 AWS runtime in Singapore: private/static S3 buckets, CloudFront OAC and security headers, Cognito, API Gateway/Lambda, workload SQS/DLQs and alarms, finite logs, ECR, Fargate Spot-compatible browser/backup tasks, daily logical backup scheduling, workload-separated IAM, and an AWS cost budget. P0 has local, CI, and production only—no permanent staging.

All runtime image inputs must be ECR URIs pinned by SHA-256 digest. Database/provider secrets already exist as SSM SecureStrings; Terraform stores parameter names, not values. DNS certificates and private-network IDs are explicit deployment inputs.

Remote state uses a separately bootstrapped private, encrypted, versioned S3 bucket with Block Public Access and S3-native locking. Supply backend values during `terraform init`; never commit state. The production GitHub workflow authenticates through OIDC, saves a reviewed plan, applies that exact plan, and records the Git SHA/digests.

```powershell
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

See `docs/runbooks/deployment-rollback.md` and `docs/runbooks/backup-restore.md` before applying.
