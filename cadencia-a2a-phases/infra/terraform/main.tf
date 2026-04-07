# ═══════════════════════════════════════════════════════════════
# Cadencia — Terraform Main Configuration
# context.md §10: ALL resources in ap-south-1 (Mumbai)
# NON-NEGOTIABLE: no data replication outside ap-south-1
# ═══════════════════════════════════════════════════════════════

terraform {
  required_version = ">= 1.7"

  backend "s3" {
    bucket         = "cadencia-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "cadencia-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-south-1"   # Mumbai — hardcoded, non-configurable

  default_tags {
    tags = {
      Project     = "cadencia"
      Environment = var.environment
      ManagedBy   = "terraform"
      DataResidency = "ap-south-1"
    }
  }
}

# ── Data Sources ───────────────────────────────────────────────

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# ── VPC ────────────────────────────────────────────────────────

module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  vpc_cidr            = "10.0.0.0/16"
  availability_zones  = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
}

# ── RDS PostgreSQL 16 + pgvector ───────────────────────────────

module "rds" {
  source = "./modules/rds"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  ecs_security_group = module.ecs.task_security_group_id

  instance_class     = "db.t3.medium"
  engine_version     = "16"
  db_name            = "cadencia"
  multi_az           = true
  storage_gb         = 100
  max_storage_gb     = 1000
  backup_retention   = 7
}

# ── ElastiCache Redis 7 ───────────────────────────────────────

module "elasticache" {
  source = "./modules/elasticache"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  ecs_security_group = module.ecs.task_security_group_id

  node_type          = "cache.t3.medium"
  engine_version     = "7.0"
}

# ── ECS Fargate ────────────────────────────────────────────────

module "ecs" {
  source = "./modules/ecs"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids
  app_version        = var.app_version
  ecr_repository_url = aws_ecr_repository.cadencia.repository_url

  cpu    = 1024    # 1 vCPU
  memory = 2048    # 2 GB

  desired_count = 2
  min_capacity  = 2
  max_capacity  = 10

  database_secret_arn = module.secrets.database_url_arn
  redis_secret_arn    = module.secrets.redis_url_arn
  openai_secret_arn   = module.secrets.openai_api_key_arn
  jwt_secret_arn      = module.secrets.jwt_private_key_arn
  mnemonic_secret_arn = module.secrets.mnemonic_arn

  health_check_path = "/health"
  domain_name       = var.domain_name
}

# ── ECR Repository ─────────────────────────────────────────────

resource "aws_ecr_repository" "cadencia" {
  name                 = "cadencia-api"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "cadencia" {
  repository = aws_ecr_repository.cadencia.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

# ── Secrets Manager ────────────────────────────────────────────

module "secrets" {
  source      = "./modules/secrets"
  environment = var.environment
}

# ── Monitoring ─────────────────────────────────────────────────

module "monitoring" {
  source = "./modules/monitoring"

  environment     = var.environment
  ecs_cluster     = module.ecs.cluster_name
  ecs_service     = module.ecs.service_name
  alb_arn_suffix  = module.ecs.alb_arn_suffix
  alert_email     = var.alert_email
  rds_instance_id = module.rds.instance_id
}

# ── CloudTrail + GuardDuty ─────────────────────────────────────

resource "aws_cloudtrail" "main" {
  name                          = "cadencia-${var.environment}"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = false   # ap-south-1 only
  enable_log_file_validation    = true
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = "cadencia-cloudtrail-${var.environment}"
  force_destroy = false
}

resource "aws_guardduty_detector" "main" {
  enable = true
}
