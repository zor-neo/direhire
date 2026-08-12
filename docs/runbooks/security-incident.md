# Security incident

Follow **Detect → Contain → Investigate → Recover → Review**. Record UTC time, safe identifiers, affected boundary, release SHA, and correlation IDs; never copy career bodies or credentials into the incident record.

1. Contain with the narrowest audited platform/source kill switch, revoke affected sessions, and disable accounts where necessary.
2. Preserve CloudWatch metadata, append-only audit records, deployment records, and relevant AWS control-plane events under approved access.
3. Determine tenant/data classes and whether signed URLs, credentials, AI routing, or deletion guarantees were affected. Admins must not inspect private career content.
4. Rotate/redeploy immutable credentials or artifacts, restore safe configuration through Terraform/PostgreSQL controls, and run focused security/tenant tests.
5. Document scope, timeline, user/compliance communication decision, corrective changes, and follow-up owner.
