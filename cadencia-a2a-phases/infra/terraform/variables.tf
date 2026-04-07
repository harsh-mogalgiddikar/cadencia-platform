# ═══════════════════════════════════════════════════════════════
# Cadencia — Terraform Variables
# ═══════════════════════════════════════════════════════════════

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "Environment must be 'production' or 'staging'."
  }
}

variable "app_version" {
  description = "Docker image tag (git commit SHA)"
  type        = string
}

variable "domain_name" {
  description = "Production domain (e.g. api.cadencia.in)"
  type        = string
  default     = "api.cadencia.in"
}

variable "alert_email" {
  description = "Email for CloudWatch alarm notifications"
  type        = string
}
