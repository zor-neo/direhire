# Credential compromise

1. Disable the affected provider/capability with its audited kill switch; never route private work to Gemini as fallback.
2. Revoke/rotate the single affected SSM SecureString in the provider console and SSM. Do not print or pass the value through Terraform state.
3. Review only metadata: provider, route, operation IDs, timestamps, token counts, errors, and CloudTrail access to the parameter.
4. Re-enable after a bounded synthetic health check and confirm old credentials fail. Review IAM access and split any over-broad workload role.
5. Record the rotation and assess whether user/provider notification is required.
