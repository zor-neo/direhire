# Production deployment and rollback

Production deployment is manual, serialized, and protected by the GitHub `production` environment. GitHub authenticates to AWS with OIDC; no long-lived AWS keys are used. The deploy role is bootstrapped separately with the least privileges needed for ECR, S3 frontend publication, CloudFront invalidation, Terraform-managed services, and `iam:PassRole` only for `direhire-prod-*` runtime roles.

## Deploy

1. Merge a commit whose CI backend, frontend, contract, and Terraform gates pass.
2. Run **Deploy production** with `apply=false`. It builds and scans immutable ECR images tagged with the Git SHA and creates a saved Terraform plan using digest-pinned image URIs.
3. Review the plan, especially IAM, public access, data lifecycle, queue mappings, budgets, and any migration.
4. Re-run for the same commit with `apply=true` after production-environment approval. Migration failure stops before frontend publication.
5. Smoke-check `/api/v1/health`, Cognito login/callback/logout, one synthetic Watch run, Inbox visibility, and private-file ownership. Record release SHA and build time.

## Rollback

Application artifacts are immutable. Select the previous known-good Git SHA and its recorded ECR digests, create a plan that points Lambda/ECS task definitions back to those digests, review, and apply. Publish the matching previously built static artifact; do not rebuild an old branch.

Schema changes follow expand/contract. Roll application code back only while the expanded schema remains compatible. A destructive database downgrade requires a separate reviewed recovery decision; never make it an automatic rollback step. After rollback, repeat smoke checks and preserve correlation IDs for any failed workflows.

## Emergency changes

The AWS console is inspection-only under normal operation. Reconcile any approved emergency change into Terraform immediately. Never put database URLs, provider keys, signed URLs, user content, or private request bodies in workflow logs or release records.
