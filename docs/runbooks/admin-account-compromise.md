# Admin account compromise

1. Disable the account, increment its security version, revoke all sessions, and remove/disable its Cognito access.
2. Review MFA events, opaque-session metadata, source/platform control changes, entitlement changes, and audit entries. Do not grant or use private career-content access.
3. Revert unauthorized operational changes through audited APIs/Terraform and rotate credentials only when evidence shows exposure.
4. Restore access through a distinct verified Superadmin with MFA; never reactivate the compromised session.
5. Capture timeline, affected operational controls, corrective action, and least-privilege follow-up.
