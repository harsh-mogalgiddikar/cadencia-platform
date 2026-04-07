# RDS Module — PostgreSQL 16 + pgvector, Multi-AZ, encrypted

variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "ecs_security_group" { type = string }
variable "instance_class" { type = string }
variable "engine_version" { type = string }
variable "db_name" { type = string }
variable "multi_az" { type = bool }
variable "storage_gb" { type = number }
variable "max_storage_gb" { type = number }
variable "backup_retention" { type = number }

resource "aws_db_subnet_group" "main" {
  name       = "cadencia-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name_prefix = "cadencia-rds-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ecs_security_group]
    description     = "PostgreSQL from ECS tasks only"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_parameter_group" "pg16" {
  family = "postgres16"
  name   = "cadencia-pg16-${var.environment}"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "vector"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"   # Log queries > 1s
  }
}

resource "aws_db_instance" "main" {
  identifier     = "cadencia-${var.environment}"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.db_name
  username = "cadencia"
  manage_master_user_password = true   # AWS manages password in Secrets Manager

  allocated_storage     = var.storage_gb
  max_allocated_storage = var.max_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.pg16.name

  backup_retention_period = var.backup_retention
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "cadencia-${var.environment}-final"

  auto_minor_version_upgrade = true
  publicly_accessible        = false
}

output "endpoint" { value = aws_db_instance.main.endpoint }
output "instance_id" { value = aws_db_instance.main.id }
