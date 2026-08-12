resource "aws_ecr_repository" "backup" {
  name                 = "direhire/database-backup"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecs_cluster" "workers" {
  name = "direhire-${var.environment}-workers"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "workers" {
  cluster_name       = aws_ecs_cluster.workers.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

resource "aws_iam_role" "ecs_execution" {
  name = "direhire-${var.environment}-ecs-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "browser_task" {
  name = "direhire-${var.environment}-browser-task"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "browser_task" {
  role = aws_iam_role.browser_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.database_url_parameter_name}"
    }]
  })
}

resource "aws_iam_role" "backup_task" {
  name = "direhire-${var.environment}-backup-task"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "backup_task" {
  role = aws_iam_role.backup_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.database_direct_url_parameter_name}" },
      { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.backups.arn}/logical/*" }
    ]
  })
}

resource "aws_cloudwatch_log_group" "ecs" {
  for_each          = toset(["browser", "backup"])
  name              = "/ecs/direhire-${var.environment}-${each.key}"
  retention_in_days = 30
}

resource "aws_ecs_task_definition" "browser" {
  family                   = "direhire-${var.environment}-browser"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.browser_task.arn
  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name      = "browser-worker"
    image     = var.browser_image_uri
    essential = true
    environment = [
      { name = "DIREHIRE_ENVIRONMENT", value = "production" },
      { name = "DIREHIRE_DATABASE_URL_PARAMETER", value = var.database_url_parameter_name }
    ]
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-region" = var.aws_region, "awslogs-group" = aws_cloudwatch_log_group.ecs["browser"].name, "awslogs-stream-prefix" = "worker" } }
    stopTimeout      = 120
  }])
}

resource "aws_ecs_task_definition" "backup" {
  family                   = "direhire-${var.environment}-backup"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.backup_task.arn
  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name      = "logical-backup"
    image     = var.backup_image_uri
    essential = true
    environment = [
      { name = "DATABASE_URL_PARAMETER", value = var.database_direct_url_parameter_name },
      { name = "BACKUP_BUCKET", value = aws_s3_bucket.backups.id }
    ]
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-region" = var.aws_region, "awslogs-group" = aws_cloudwatch_log_group.ecs["backup"].name, "awslogs-stream-prefix" = "backup" } }
  }])
}

resource "aws_iam_role" "ecs_scheduler" {
  name = "direhire-${var.environment}-ecs-scheduler"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "scheduler.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "ecs_scheduler" {
  role = aws_iam_role.ecs_scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecs:RunTask"], Resource = aws_ecs_task_definition.backup.arn },
      { Effect = "Allow", Action = ["iam:PassRole"], Resource = [aws_iam_role.ecs_execution.arn, aws_iam_role.backup_task.arn] }
    ]
  })
}

resource "aws_scheduler_schedule" "backup" {
  name                = "direhire-${var.environment}-logical-backup"
  schedule_expression = "cron(15 19 * * ? *)"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_ecs_cluster.workers.arn
    role_arn = aws_iam_role.ecs_scheduler.arn
    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.backup.arn
      task_count          = 1
      launch_type         = "FARGATE"
      network_configuration {
        subnets          = var.private_subnet_ids
        security_groups  = var.browser_security_group_ids
        assign_public_ip = true
      }
    }
  }
}

# No ECS service is created for browser work. The task definition is launched only
# when a reviewed browser-required adapter has queued work, so steady-state cost is zero.
output "browser_task_definition_arn" { value = aws_ecs_task_definition.browser.arn }
output "backup_repository_url" { value = aws_ecr_repository.backup.repository_url }
