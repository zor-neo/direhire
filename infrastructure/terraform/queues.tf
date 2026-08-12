locals {
  queues = {
    source-discovery = { visibility_timeout = 180, age_alarm_seconds = 300 }
    ai-analysis      = { visibility_timeout = 300, age_alarm_seconds = 600 }
    interactive-ai   = { visibility_timeout = 180, age_alarm_seconds = 120 }
    notification     = { visibility_timeout = 120, age_alarm_seconds = 300 }
    documents        = { visibility_timeout = 300, age_alarm_seconds = 600 }
    maintenance      = { visibility_timeout = 300, age_alarm_seconds = 1800 }
  }
}

resource "aws_sqs_queue" "dlq" {
  for_each = local.queues

  name                      = "direhire-${var.environment}-${each.key}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "workload" {
  for_each = local.queues

  name                       = "direhire-${var.environment}-${each.key}"
  visibility_timeout_seconds = each.value.visibility_timeout
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "workload" {
  for_each = local.queues

  queue_url = aws_sqs_queue.dlq[each.key].id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.workload[each.key].arn]
  })
}

resource "aws_cloudwatch_metric_alarm" "queue_age" {
  for_each = local.queues

  alarm_name          = "direhire-${var.environment}-${each.key}-oldest-message"
  alarm_description   = "Oldest ${each.key} message exceeds the expected processing window."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = aws_sqs_queue.workload[each.key].name }
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  period              = 60
  statistic           = "Maximum"
  threshold           = each.value.age_alarm_seconds
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

resource "aws_cloudwatch_metric_alarm" "dlq_visible" {
  for_each = local.queues

  alarm_name          = "direhire-${var.environment}-${each.key}-dlq-visible"
  alarm_description   = "The ${each.key} dead-letter queue contains a failed message."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.dlq[each.key].name }
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns
}

output "queue_urls" {
  description = "Workload queue URLs for runtime configuration."
  value       = { for key, queue in aws_sqs_queue.workload : key => queue.url }
}

