# ECS Fargate Module — cluster, service, ALB, auto-scaling, IAM

variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "app_version" { type = string }
variable "ecr_repository_url" { type = string }
variable "cpu" { type = number }
variable "memory" { type = number }
variable "desired_count" { type = number }
variable "min_capacity" { type = number }
variable "max_capacity" { type = number }
variable "database_secret_arn" { type = string }
variable "redis_secret_arn" { type = string }
variable "openai_secret_arn" { type = string }
variable "jwt_secret_arn" { type = string }
variable "mnemonic_secret_arn" { type = string }
variable "health_check_path" { type = string }
variable "domain_name" { type = string }

# ── ECS Cluster ────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "cadencia-${var.environment}"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ── Security Group ─────────────────────────────────────────────

resource "aws_security_group" "ecs_tasks" {
  name_prefix = "cadencia-ecs-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "API from ALB only"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Outbound: RDS, Redis, Algorand, OpenAI"
  }
}

resource "aws_security_group" "alb" {
  name_prefix = "cadencia-alb-"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from anywhere"
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP redirect"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── IAM Roles ──────────────────────────────────────────────────

resource "aws_iam_role" "task_execution" {
  name = "cadencia-task-execution-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution_base" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        var.database_secret_arn,
        var.redis_secret_arn,
        var.openai_secret_arn,
        var.jwt_secret_arn,
        var.mnemonic_secret_arn,
      ]
    }]
  })
}

resource "aws_iam_role" "task_role" {
  name = "cadencia-task-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# ── CloudWatch Log Group ──────────────────────────────────────

resource "aws_cloudwatch_log_group" "api" {
  name              = "/cadencia/api-${var.environment}"
  retention_in_days = 90
}

resource "aws_cloudwatch_log_group" "migration" {
  name              = "/cadencia/migration-${var.environment}"
  retention_in_days = 30
}

# ── ALB ────────────────────────────────────────────────────────

resource "aws_lb" "main" {
  name               = "cadencia-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "cadencia-api-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}

# ── Task Definitions ──────────────────────────────────────────

resource "aws_ecs_task_definition" "api" {
  family                   = "cadencia-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([{
    name  = "cadencia-api"
    image = "${var.ecr_repository_url}:${var.app_version}"
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    essential = true

    secrets = [
      { name = "DATABASE_URL", valueFrom = var.database_secret_arn },
      { name = "REDIS_URL",    valueFrom = var.redis_secret_arn },
      { name = "OPENAI_API_KEY", valueFrom = var.openai_secret_arn },
      { name = "JWT_PRIVATE_KEY", valueFrom = var.jwt_secret_arn },
      { name = "ALGORAND_ESCROW_CREATOR_MNEMONIC", valueFrom = var.mnemonic_secret_arn },
    ]

    environment = [
      { name = "APP_ENV",       value = var.environment },
      { name = "APP_VERSION",   value = var.app_version },
      { name = "LLM_PROVIDER",  value = "stub" },
      { name = "DATA_RESIDENCY_REGION", value = "ap-south-1" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = "ap-south-1"
        "awslogs-stream-prefix" = "api"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 60
    }
  }])
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "cadencia-migration"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.task_execution.arn

  container_definitions = jsonencode([{
    name      = "cadencia-migration"
    image     = "${var.ecr_repository_url}:${var.app_version}"
    essential = true
    command   = ["python", "-m", "alembic", "upgrade", "head"]

    secrets = [
      { name = "DATABASE_URL", valueFrom = var.database_secret_arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.migration.name
        "awslogs-region"        = "ap-south-1"
        "awslogs-stream-prefix" = "migration"
      }
    }
  }])
}

# ── ECS Service ────────────────────────────────────────────────

resource "aws_ecs_service" "api" {
  name            = "cadencia-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 60

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "cadencia-api"
    container_port   = 8000
  }
}

# ── Auto-Scaling ──────────────────────────────────────────────

resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "cadencia-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_policy" "alb_requests" {
  name               = "cadencia-alb-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.main.arn_suffix}/${aws_lb_target_group.api.arn_suffix}"
    }
    target_value       = 1000.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# ── Outputs ────────────────────────────────────────────────────

output "cluster_name" { value = aws_ecs_cluster.main.name }
output "service_name" { value = aws_ecs_service.api.name }
output "task_security_group_id" { value = aws_security_group.ecs_tasks.id }
output "alb_dns_name" { value = aws_lb.main.dns_name }
output "alb_arn_suffix" { value = aws_lb.main.arn_suffix }
