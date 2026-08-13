locals {
  event_queue_routes = {
    "watch.discovery.requested"       = aws_sqs_queue.workload["source-discovery"].url
    "analyze.job.requested"           = aws_sqs_queue.workload["source-discovery"].url
    "job.analysis.requested"          = aws_sqs_queue.workload["ai-analysis"].url
    "private.ai.requested"            = aws_sqs_queue.workload["interactive-ai"].url
    "watch.query-expansion.requested" = aws_sqs_queue.workload["interactive-ai"].url
    "notification.digest.requested"   = aws_sqs_queue.workload["notification"].url
    "private.document.requested"      = aws_sqs_queue.workload["documents"].url
    "file.scan.requested"             = aws_sqs_queue.workload["documents"].url
    "privacy.export.requested"        = aws_sqs_queue.workload["maintenance"].url
    "privacy.deletion.requested"      = aws_sqs_queue.workload["maintenance"].url
  }
  lambda_workloads = {
    source-discovery = { timeout = 150, memory = 1024, concurrency = 4 }
    ai-analysis      = { timeout = 240, memory = 1024, concurrency = 6 }
    interactive-ai   = { timeout = 150, memory = 1024, concurrency = 6 }
    notification     = { timeout = 90, memory = 512, concurrency = 4 }
    documents        = { timeout = 240, memory = 1536, concurrency = 3 }
    maintenance      = { timeout = 240, memory = 1024, concurrency = 2 }
  }
  common_environment = {
    DIREHIRE_ENVIRONMENT                  = "production"
    DIREHIRE_DATABASE_URL_PARAMETER       = var.database_url_parameter_name
    DIREHIRE_CORS_ORIGINS                 = jsonencode(["https://${var.frontend_domain_name}"])
    DIREHIRE_FRONTEND_POST_LOGIN_URL      = "https://${var.frontend_domain_name}/dashboard/"
    DIREHIRE_COGNITO_DOMAIN               = "https://${aws_cognito_user_pool_domain.hosted.domain}.auth.${var.aws_region}.amazoncognito.com"
    DIREHIRE_COGNITO_USER_POOL_ID         = aws_cognito_user_pool.users.id
    DIREHIRE_COGNITO_CLIENT_ID            = aws_cognito_user_pool_client.web.id
    DIREHIRE_COGNITO_REDIRECT_URI         = "https://${var.api_domain_name}/api/v1/auth/callback"
    DIREHIRE_PRIVATE_BUCKET_NAME          = aws_s3_bucket.private.id
    DIREHIRE_QUEUE_ROUTES                 = jsonencode(local.event_queue_routes)
    DIREHIRE_USAJOBS_ENABLED              = tostring(var.usajobs_enabled)
    DIREHIRE_USAJOBS_API_KEY_PARAMETER    = var.usajobs_api_key_parameter_name
    DIREHIRE_USAJOBS_USER_AGENT_PARAMETER = var.usajobs_user_agent_parameter_name
  }
}

resource "aws_ecr_repository" "runtime" {
  name                 = "direhire/runtime"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_repository" "browser" {
  name                 = "direhire/browser-worker"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_lifecycle_policy" "images" {
  for_each   = { runtime = aws_ecr_repository.runtime.name, browser = aws_ecr_repository.browser.name }
  repository = each.value
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the latest 20 immutable releases"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_iam_role" "api" {
  name = "direhire-${var.environment}-api"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role" "worker" {
  for_each = local.lambda_workloads
  name     = "direhire-${var.environment}-${each.key}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role" "pump" {
  name = "direhire-${var.environment}-workflow-pump"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "worker_logs" {
  for_each   = local.lambda_workloads
  role       = aws_iam_role.worker[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "pump_logs" {
  role       = aws_iam_role.pump.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "api_data" {
  name = "direhire-${var.environment}-api-data"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.database_url_parameter_name}" },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.private.arn}/*" }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_data" {
  role       = aws_iam_role.api.name
  policy_arn = aws_iam_policy.api_data.arn
}

resource "aws_iam_role_policy" "worker" {
  for_each = local.lambda_workloads
  role     = aws_iam_role.worker[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"]
        Resource = aws_sqs_queue.workload[each.key].arn
        }, {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.database_url_parameter_name}"
      }],
      contains(["ai-analysis"], each.key) ? [{
        Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/prod/ai/gemini/public/*"
      }] : [],
      contains(["interactive-ai"], each.key) ? [{
        Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/prod/ai/openrouter/private/*"
      }] : [],
      contains(["notification"], each.key) ? [{
        Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/prod/notifications/*"
      }] : [],
      contains(["source-discovery"], each.key) && var.usajobs_enabled ? [{
        Effect = "Allow", Action = ["ssm:GetParameter"], Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.usajobs_api_key_parameter_name}",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.usajobs_user_agent_parameter_name}"
        ]
      }] : [],
      contains(["documents", "maintenance"], each.key) ? [{
        Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.private.arn}/*"
      }] : []
    )
  })
}

resource "aws_iam_role_policy" "pump" {
  role = aws_iam_role.pump.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.database_url_parameter_name}" },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [for queue in aws_sqs_queue.workload : queue.arn] }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "direhire-${var.environment}-api"
  package_type  = "Image"
  image_uri     = var.runtime_image_uri
  role          = aws_iam_role.api.arn
  timeout       = 29
  memory_size   = 1024
  architectures = ["x86_64"]
  image_config { command = ["direhire.main.handler"] }
  environment { variables = local.common_environment }
  depends_on = [aws_iam_role_policy_attachment.api_logs]
}

resource "aws_lambda_function" "worker" {
  for_each = local.lambda_workloads

  function_name = "direhire-${var.environment}-${each.key}"
  package_type  = "Image"
  image_uri     = var.runtime_image_uri
  role          = aws_iam_role.worker[each.key].arn
  timeout       = each.value.timeout
  memory_size   = each.value.memory
  architectures = ["x86_64"]
  image_config { command = ["direhire.workers.runtime.lambda_handler"] }
  environment { variables = merge(local.common_environment, { DIREHIRE_WORKLOAD = each.key }) }
  depends_on = [aws_iam_role_policy_attachment.worker_logs]
}

resource "aws_lambda_event_source_mapping" "worker" {
  for_each = local.lambda_workloads

  event_source_arn                   = aws_sqs_queue.workload[each.key].arn
  function_name                      = aws_lambda_function.worker[each.key].arn
  batch_size                         = each.key == "notification" ? 5 : 1
  maximum_batching_window_in_seconds = 1
  function_response_types            = ["ReportBatchItemFailures"]
  scaling_config { maximum_concurrency = each.value.concurrency }
}

resource "aws_lambda_function" "pump" {
  function_name = "direhire-${var.environment}-workflow-pump"
  package_type  = "Image"
  image_uri     = var.runtime_image_uri
  role          = aws_iam_role.pump.arn
  timeout       = 55
  memory_size   = 512
  architectures = ["x86_64"]
  image_config { command = ["direhire.workers.maintenance.lambda_handler"] }
  environment { variables = local.common_environment }
  depends_on = [aws_iam_role_policy_attachment.pump_logs]
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = merge(
    { api = aws_lambda_function.api.function_name, pump = aws_lambda_function.pump.function_name },
    { for key, function in aws_lambda_function.worker : key => function.function_name }
  )
  name              = "/aws/lambda/${each.value}"
  retention_in_days = 30
}

resource "aws_scheduler_schedule" "workflow_pump" {
  name                = "direhire-${var.environment}-workflow-pump"
  schedule_expression = "rate(1 minute)"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_lambda_function.pump.arn
    role_arn = aws_iam_role.scheduler.arn
  }
}

resource "aws_iam_role" "scheduler" {
  name = "direhire-${var.environment}-scheduler"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "scheduler.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = aws_lambda_function.pump.arn }]
  })
}

resource "aws_apigatewayv2_api" "http" {
  name          = "direhire-${var.environment}"
  protocol_type = "HTTP"
  cors_configuration {
    allow_credentials = true
    allow_headers     = ["Content-Type", "X-CSRF-Token", "X-Correlation-ID"]
    allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_origins     = ["https://${var.frontend_domain_name}"]
    max_age           = 600
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId = "$context.requestId", routeKey = "$context.routeKey", status = "$context.status", responseLatency = "$context.responseLatency"
    })
  }
  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/direhire-${var.environment}"
  retention_in_days = 30
}

resource "aws_apigatewayv2_domain_name" "api" {
  domain_name = var.api_domain_name
  domain_name_configuration {
    certificate_arn = var.api_certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  api_id      = aws_apigatewayv2_api.http.id
  domain_name = aws_apigatewayv2_domain_name.api.id
  stage       = aws_apigatewayv2_stage.prod.id
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "api_gateway_target" { value = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name }
output "runtime_repository_url" { value = aws_ecr_repository.runtime.repository_url }
output "browser_repository_url" { value = aws_ecr_repository.browser.repository_url }
