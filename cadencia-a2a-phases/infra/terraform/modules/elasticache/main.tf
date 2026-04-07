# ElastiCache Module — Redis 7, encrypted, auth token

variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "ecs_security_group" { type = string }
variable "node_type" { type = string }
variable "engine_version" { type = string }

resource "aws_elasticache_subnet_group" "main" {
  name       = "cadencia-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name_prefix = "cadencia-redis-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.ecs_security_group]
    description     = "Redis from ECS tasks only"
  }
}

resource "aws_elasticache_parameter_group" "redis7" {
  family = "redis7"
  name   = "cadencia-redis7-${var.environment}"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "cadencia-${var.environment}"
  description          = "Cadencia Redis — ${var.environment}"

  node_type            = var.node_type
  num_cache_clusters   = 1   # Single node (add replica later)
  engine_version       = var.engine_version
  parameter_group_name = aws_elasticache_parameter_group.redis7.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  automatic_failover_enabled = false   # Single node
  multi_az_enabled           = false

  maintenance_window = "sun:05:00-sun:06:00"
  snapshot_retention_limit = 3
}

output "endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}
