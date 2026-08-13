# Authentication and verification delivery

DireHire uses Cognito managed login v2 with Authorization Code + PKCE. Cognito, not the application, receives passwords. MFA is optional for normal users; TOTP remains mandatory before an `ADMIN` or `SUPERADMIN` session is authorized.

Verification messages use the branded Cognito template even while the pool uses the default sender. The default sender is suitable only for early validation and has limited deliverability control.

Before switching production to SES:

1. verify the intended sending domain in SES in `ap-southeast-1`;
2. publish all SES DKIM records and the domain SPF/DMARC policy in authoritative DNS;
3. request SES production sending access;
4. verify delivery to Gmail, Outlook, and a private-domain mailbox, including spam placement;
5. set `cognito_ses_email_configuration` to the verified identity ARN and branded From address;
6. review and apply Terraform, then repeat the delivery checks.

Terraform creates the `auth.zorneo.dev` identity and exposes `auth_email_dns_records`.
Publish those records as DNS-only records in Cloudflare. Do not proxy DKIM CNAME records.
After SES reports `SUCCESS` and `VerifiedForSendingStatus=true`, set:

```hcl
cognito_ses_email_configuration = {
  source_arn             = "<auth_email_identity_arn output>"
  from_email_address     = "DireHire <no-reply@auth.zorneo.dev>"
  reply_to_email_address = "support@zorneo.dev"
}
```

Do not configure an unverified identity or silently fall back to a different sending domain.
