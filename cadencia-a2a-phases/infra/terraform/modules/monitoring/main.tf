# Monitoring Module — CloudWatch alarms, SNS, log groups

variable "environment" { type = string }
variable "ecs_cluster" { type = string }
variable "ecs_service" { type = string }
variable "alb_arn_suffix" { type = string }
variable "alert_email" { type = string }
variable "rds_instance_id" { type = string }

# ── SNS Topic ──────────────────────────────────────────────────

resource "aws_sns_topic" "alerts" {
  name = "cadencia-alerts-${var.environment}"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── Sev-1 Alarms ──────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "high_5xx_rate" {
  alarm_name          = "cadencia-5xx-rate-critical"
  alarm_description   = "Sev-1: 5xx error rate > 10% for 2 min"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 10
  period              = 60

  metric_name = "HTTPCode_Target_5XX_Count"
  namespace   = "AWS/ApplicationELB"
  statistic   = "Sum"
  dimensions  = { LoadBalancer = var.alb_arn_suffix }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# ── Sev-2 Alarms ──────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "elevated_5xx" {
  alarm_name          = "cadencia-5xx-rate-elevated"
  alarm_description   = "Sev-2: 5xx error rate > 1% for 5 min"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  threshold           = 1
  period              = 60

  metric_name = "HTTPCode_Target_5XX_Count"
  namespace   = "AWS/ApplicationELB"
  statistic   = "Sum"
  dimensions  = { LoadBalancer = var.alb_arn_suffix }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ecs_task_failures" {
  alarm_name          = "cadencia-ecs-task-failures"
  alarm_description   = "Sev-2: ECS task stopped unexpectedly"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  period              = 300

  metric_name = "CPUUtilization"
  namespace   = "AWS/ECS"
  statistic   = "SampleCount"
  dimensions = {
    ClusterName = var.ecs_cluster
    ServiceName = var.ecs_service
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# ── Sev-3 Alarms ──────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "high_latency" {
  alarm_name          = "cadencia-latency-p95"
  alarm_description   = "Sev-3: p95 latency > 500ms for 15 min"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 15
  threshold           = 0.5
  period              = 60

  metric_name = "TargetResponseTime"
  namespace   = "AWS/ApplicationELB"
  statistic   = "p95"
  dimensions  = { LoadBalancer = var.alb_arn_suffix }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "cadencia-rds-cpu"
  alarm_description   = "Sev-3: RDS CPU > 80% for 10 min"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 10
  threshold           = 80
  period              = 60

  metric_name = "CPUUtilization"
  namespace   = "AWS/RDS"
  statistic   = "Average"
  dimensions  = { DBInstanceIdentifier = var.rds_instance_id }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# ── CloudWatch Dashboard ──────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "cadencia-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x = 0, y = 0, width = 12, height = 6
        properties = {
          title   = "Request Count"
          metrics = [["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "Sum"
        }
      },
      {
        type   = "metric"
        x = 12, y = 0, width = 12, height = 6
        properties = {
          title   = "5xx Errors"
          metrics = [["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "Sum"
        }
      },
      {
        type   = "metric"
        x = 0, y = 6, width = 12, height = 6
        properties = {
          title   = "Response Time p95"
          metrics = [["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "p95"
        }
      },
      {
        type   = "metric"
        x = 12, y = 6, width = 12, height = 6
        properties = {
          title   = "ECS CPU Utilization"
          metrics = [["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster, "ServiceName", var.ecs_service]]
          period  = 60
          stat    = "Average"
        }
      },
      {
        type   = "metric"
        x = 0, y = 12, width = 12, height = 6
        properties = {
          title   = "RDS CPU"
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_instance_id]]
          period  = 60
          stat    = "Average"
        }
      }
    ]
  })
}
