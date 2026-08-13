resource "aws_cognito_user_pool" "users" {
  name                     = "direhire-${var.environment}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  # Normal users may opt into TOTP. Application authorization still requires
  # verified MFA before ADMIN or SUPERADMIN access is usable.
  mfa_configuration = "OPTIONAL"
  user_pool_tier    = "ESSENTIALS"

  software_token_mfa_configuration { enabled = true }
  email_configuration {
    email_sending_account  = var.cognito_ses_email_configuration == null ? "COGNITO_DEFAULT" : "DEVELOPER"
    source_arn             = var.cognito_ses_email_configuration == null ? null : var.cognito_ses_email_configuration.source_arn
    from_email_address     = var.cognito_ses_email_configuration == null ? null : var.cognito_ses_email_configuration.from_email_address
    reply_to_email_address = var.cognito_ses_email_configuration == null ? null : var.cognito_ses_email_configuration.reply_to_email_address
  }
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Verify your email for DireHire"
    email_message        = <<-HTML
      <div style="margin:0;padding:32px 16px;background:#f5f7f4;font-family:Arial,sans-serif;color:#1b2420">
        <div style="max-width:520px;margin:0 auto;padding:32px;background:#ffffff;border:1px solid #dbe3dd;border-radius:16px">
          <div style="display:inline-block;margin-bottom:24px;padding:8px 12px;border-radius:10px;background:#146c4e;color:#ffffff;font-weight:700">DireHire</div>
          <h1 style="margin:0 0 12px;font-size:24px;line-height:1.25">Verify your email</h1>
          <p style="margin:0 0 24px;color:#536159;line-height:1.6">Enter this code in the DireHire sign-up window to finish creating your account.</p>
          <div style="margin:0 0 24px;padding:16px;border-radius:12px;background:#edf5f0;text-align:center;font-size:28px;font-weight:700;letter-spacing:8px;color:#0e5340">{####}</div>
          <p style="margin:0;color:#718078;font-size:13px;line-height:1.5">If you did not request this account, you can safely ignore this email. DireHire will never ask you to send this code to another person.</p>
        </div>
      </div>
    HTML
  }
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 2
  }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }
  deletion_protection = "ACTIVE"
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "direhire-${var.environment}-web"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = false
  supported_identity_providers         = ["COGNITO"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["https://${var.api_domain_name}/api/v1/auth/callback"]
  logout_urls                          = ["https://${var.frontend_domain_name}"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 7
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_pool_domain" "hosted" {
  domain                = var.cognito_domain_prefix
  user_pool_id          = aws_cognito_user_pool.users.id
  managed_login_version = 2
}

# Managed login v2 provides the current responsive Cognito experience. Branding
# remains Terraform-owned and can accept explicit assets/settings later.
resource "aws_cognito_managed_login_branding" "web" {
  client_id                   = aws_cognito_user_pool_client.web.id
  user_pool_id                = aws_cognito_user_pool.users.id
  use_cognito_provided_values = true

  depends_on = [aws_cognito_user_pool_domain.hosted]
}

output "cognito_user_pool_id" { value = aws_cognito_user_pool.users.id }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
