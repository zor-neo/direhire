data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "frontend" {
  bucket = "direhire-${var.environment}-${data.aws_caller_identity.current.account_id}-frontend"
}

resource "aws_s3_bucket" "private" {
  bucket = "direhire-${var.environment}-${data.aws_caller_identity.current.account_id}-private"
}

resource "aws_s3_bucket" "backups" {
  bucket = "direhire-${var.environment}-${data.aws_caller_identity.current.account_id}-backups"
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = {
    frontend = aws_s3_bucket.frontend.id
    private  = aws_s3_bucket.private.id
    backups  = aws_s3_bucket.backups.id
  }

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = {
    frontend = aws_s3_bucket.frontend.id
    private  = aws_s3_bucket.private.id
    backups  = aws_s3_bucket.backups.id
  }
  bucket = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "private" {
  bucket = aws_s3_bucket.private.id
  rule {
    id     = "expire-temporary-private-artifacts"
    status = "Enabled"
    filter { prefix = "temporary/" }
    expiration { days = 2 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
  rule {
    id     = "expire-exports"
    status = "Enabled"
    filter { prefix = "exports/" }
    expiration { days = 2 }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    id     = "short-backup-retention"
    status = "Enabled"
    filter {}
    expiration { days = 14 }
    noncurrent_version_expiration { noncurrent_days = 7 }
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "direhire-${var.environment}-frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "direhire-${var.environment}-security"
  security_headers_config {
    content_security_policy {
      # Next.js static export emits inline bootstrap scripts for client hydration.
      # Keep script origins restricted to this site while permitting those bootstraps.
      content_security_policy = "default-src 'self'; script-src 'self' 'unsafe-inline'; connect-src 'self' https://${var.api_domain_name}; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
      override                = true
    }
    content_type_options { override = true }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }
  custom_headers_config {
    items {
      header   = "Permissions-Policy"
      value    = "camera=(), microphone=(), geolocation=()"
      override = true
    }
  }
}

resource "aws_cloudfront_function" "static_routes" {
  name    = "direhire-${var.environment}-static-routes"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-JS
    function handler(event) {
      var request = event.request;
      if (request.uri.endsWith('/')) request.uri += 'index.html';
      else if (!request.uri.includes('.')) request.uri += '/index.html';
      return request;
    }
  JS
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = [var.frontend_domain_name]
  price_class         = "PriceClass_200"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }
  default_cache_behavior {
    target_origin_id           = "frontend-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD", "OPTIONS"]
    compress                   = true
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.static_routes.arn
    }
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    acm_certificate_arn      = var.cloudfront_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/404.html"
    error_caching_min_ttl = 30
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontReadOnly"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn } }
    }]
  })
}

output "frontend_distribution_domain" { value = aws_cloudfront_distribution.frontend.domain_name }
output "private_bucket_name" { value = aws_s3_bucket.private.id }
output "backup_bucket_name" { value = aws_s3_bucket.backups.id }
