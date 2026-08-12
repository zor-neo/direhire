variable "aws_region" {
  description = "Primary AWS region. P0 uses Singapore."
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Deployment environment. Permanent staging is outside P0."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["prod"], var.environment)
    error_message = "P0 only defines the production environment; use local/CI for non-production work."
  }
}

variable "alarm_topic_arns" {
  description = "SNS topic ARNs that receive operational alarms. Empty only before alert routing is configured."
  type        = list(string)
  default     = []
}

variable "frontend_domain_name" {
  description = "Public frontend DNS name."
  type        = string
}

variable "api_domain_name" {
  description = "Public API DNS name."
  type        = string
}

variable "cloudfront_certificate_arn" {
  description = "ACM certificate ARN in us-east-1 for the frontend domain."
  type        = string
}

variable "api_certificate_arn" {
  description = "Regional ACM certificate ARN for the API domain."
  type        = string
}

variable "runtime_image_uri" {
  description = "Immutable ECR image URI pinned by digest for API and lightweight workers."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.runtime_image_uri))
    error_message = "runtime_image_uri must be immutable and pinned by sha256 digest."
  }
}

variable "browser_image_uri" {
  description = "Immutable ECR image URI pinned by digest for the browser worker."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.browser_image_uri))
    error_message = "browser_image_uri must be immutable and pinned by sha256 digest."
  }
}

variable "backup_image_uri" {
  description = "Immutable ECR image URI pinned by digest for logical database backups."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.backup_image_uri))
    error_message = "backup_image_uri must be immutable and pinned by sha256 digest."
  }
}

variable "database_url_parameter_name" {
  description = "Existing SSM SecureString containing the pooled Neon SQLAlchemy URL with sslmode=require."
  type        = string
  default     = "/prod/database/neon/pooled-url"
}

variable "database_direct_url_parameter_name" {
  description = "Existing SSM SecureString containing the direct Neon PostgreSQL URL for migrations and logical backup."
  type        = string
  default     = "/prod/database/neon/direct-url"
}

variable "cognito_domain_prefix" {
  description = "Globally unique Cognito hosted UI domain prefix."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly AWS cost budget for the P0 environment."
  type        = number
  default     = 150
}

variable "budget_alert_emails" {
  description = "Operational email recipients for AWS budget alerts."
  type        = list(string)
  default     = []
}

variable "private_subnet_ids" {
  description = "Private subnet IDs used only by the Fargate Spot browser worker."
  type        = list(string)
}

variable "browser_security_group_ids" {
  description = "Outbound-only security groups for the browser worker."
  type        = list(string)
}
