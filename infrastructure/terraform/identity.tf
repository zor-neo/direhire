resource "aws_cognito_user_pool" "users" {
  name                     = "direhire-${var.environment}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "ON"

  software_token_mfa_configuration { enabled = true }
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
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.users.id
}

# Classic hosted UI keeps Cognito responsible for credentials while matching the
# application palette. Cognito intentionally permits only its documented class
# and property allowlist here.
resource "aws_cognito_user_pool_ui_customization" "web" {
  client_id    = aws_cognito_user_pool_client.web.id
  user_pool_id = aws_cognito_user_pool_domain.hosted.user_pool_id
  css          = <<-CSS
    .background-customizable { background-color: #f5f7f4; }
    .banner-customizable { padding: 24px 0 16px 0; background-color: #ffffff; }
    .label-customizable { font-weight: 600; color: #1b2420; }
    .inputField-customizable { width: 100%; height: 44px; color: #1b2420; background-color: #ffffff; border: 1px solid #cbd5cd; }
    .inputField-customizable:focus { border-color: #146c4e; outline: 2px; }
    .submitButton-customizable { font-size: 16px; font-weight: bold; margin: 16px 0 8px 0; width: 100%; height: 44px; color: #ffffff; background-color: #146c4e; }
    .submitButton-customizable:hover { color: #ffffff; background-color: #0e5340; }
    .textDescription-customizable { padding-top: 4px; padding-bottom: 12px; display: block; font-size: 14px; color: #64716a; }
    .redirect-customizable { color: #146c4e; }
    .errorMessage-customizable { margin: 8px 0 8px 0; padding: 12px; font-size: 14px; width: 100%; background: #faeaea; border: 1px solid #b03232; color: #8f2727; box-sizing: border-box; }
    .passwordCheck-valid-customizable { color: #146c4e; }
    .passwordCheck-notValid-customizable { color: #b03232; }
  CSS
}

output "cognito_user_pool_id" { value = aws_cognito_user_pool.users.id }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
