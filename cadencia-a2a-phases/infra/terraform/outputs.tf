# ═══════════════════════════════════════════════════════════════
# Cadencia — Terraform Outputs
# ═══════════════════════════════════════════════════════════════

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "alb_dns_name" {
  value       = module.ecs.alb_dns_name
  description = "ALB DNS name — point Caddy/DNS here"
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = module.elasticache.endpoint
  sensitive = true
}

output "ecr_repository_url" {
  value = aws_ecr_repository.cadencia.repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecs_service_name" {
  value = module.ecs.service_name
}
