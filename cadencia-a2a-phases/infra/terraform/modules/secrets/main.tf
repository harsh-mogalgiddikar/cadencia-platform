# Secrets Manager Module — one secret per value (least-privilege IAM)

variable "environment" { type = string }

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "cadencia/${var.environment}/database_url"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "cadencia/${var.environment}/redis_url"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "cadencia/${var.environment}/openai_api_key"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "jwt_private_key" {
  name                    = "cadencia/${var.environment}/jwt_private_key"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "mnemonic" {
  name                    = "cadencia/${var.environment}/escrow_mnemonic"
  recovery_window_in_days = 7
}

output "database_url_arn" { value = aws_secretsmanager_secret.database_url.arn }
output "redis_url_arn" { value = aws_secretsmanager_secret.redis_url.arn }
output "openai_api_key_arn" { value = aws_secretsmanager_secret.openai_api_key.arn }
output "jwt_private_key_arn" { value = aws_secretsmanager_secret.jwt_private_key.arn }
output "mnemonic_arn" { value = aws_secretsmanager_secret.mnemonic.arn }
