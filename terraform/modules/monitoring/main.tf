variable "project_id" {}
variable "environment" {}
variable "alert_email" {}
variable "backend_service_name" {}
variable "worker_service_name" {}
variable "queue_name" {}

# --- Notification channel (email) -------------------------------------------
resource "google_monitoring_notification_channel" "email" {
  display_name = "Y2D Alerts (${var.environment})"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

# --- Uptime checks ----------------------------------------------------------
resource "google_monitoring_uptime_check_config" "backend" {
  display_name = "Y2D backend healthz (${var.environment})"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/healthz"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = "${var.backend_service_name}.run.app"
    }
  }
}

# --- Log-based metric: transfer failures ------------------------------------
resource "google_logging_metric" "transfer_errors" {
  name        = "y2d/transfer_errors_${var.environment}"
  description = "Worker transfer failures — status=error in worker logs"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.worker_service_name}"
    jsonPayload.status="error"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "transfer_id"
      value_type  = "STRING"
      description = "Transfer ID"
    }
  }

  label_extractors = {
    "transfer_id" = "EXTRACT(jsonPayload.transfer_id)"
  }
}

# --- Log-based metric: transfer completions ---------------------------------
resource "google_logging_metric" "transfer_completions" {
  name        = "y2d/transfer_completions_${var.environment}"
  description = "Successful transfer completions"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.worker_service_name}"
    jsonPayload.status="done"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# --- Alert: backend uptime --------------------------------------------------
resource "google_monitoring_alert_policy" "backend_uptime" {
  display_name = "[${var.environment}] Backend down"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failed"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\""
      duration        = "120s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_TRUE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  severity              = "CRITICAL"
}

# --- Alert: high transfer error rate ----------------------------------------
resource "google_monitoring_alert_policy" "transfer_error_rate" {
  display_name = "[${var.environment}] High transfer error rate"
  combiner     = "OR"

  conditions {
    display_name = "Transfer errors > 5 in 10 minutes"
    condition_threshold {
      filter     = "metric.type=\"logging.googleapis.com/user/y2d/transfer_errors_${var.environment}\""
      duration   = "0s"
      comparison = "COMPARISON_GT"
      threshold_value = 5
      aggregations {
        alignment_period   = "600s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  severity              = "WARNING"
}

# --- Alert: Cloud Run worker error rate -------------------------------------
resource "google_monitoring_alert_policy" "worker_error_rate" {
  display_name = "[${var.environment}] Worker 5xx error rate"
  combiner     = "OR"

  conditions {
    display_name = "Worker 5xx > 10% of requests"
    condition_threshold {
      filter     = <<-EOT
        metric.type="run.googleapis.com/request_count"
        resource.type="cloud_run_revision"
        resource.labels.service_name="${var.worker_service_name}"
        metric.labels.response_code_class="5xx"
      EOT
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.1
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  severity              = "WARNING"
}

# --- Alert: Redis memory > 80% ----------------------------------------------
resource "google_monitoring_alert_policy" "redis_memory" {
  display_name = "[${var.environment}] Redis memory > 80%"
  combiner     = "OR"

  conditions {
    display_name = "Redis memory usage high"
    condition_threshold {
      filter     = <<-EOT
        metric.type="redis.googleapis.com/stats/memory/usage_ratio"
        resource.type="redis_instance"
      EOT
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  severity              = "WARNING"
}

# --- Dashboard --------------------------------------------------------------
resource "google_monitoring_dashboard" "y2d" {
  dashboard_json = jsonencode({
    displayName = "Y2D (${var.environment})"
    gridLayout = {
      columns = 2
      widgets = [
        {
          title = "Transfer completions"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"logging.googleapis.com/user/y2d/transfer_completions_${var.environment}\""
                  aggregation = {
                    alignmentPeriod  = "3600s"
                    perSeriesAligner = "ALIGN_DELTA"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Transfer errors"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"logging.googleapis.com/user/y2d/transfer_errors_${var.environment}\""
                  aggregation = {
                    alignmentPeriod  = "3600s"
                    perSeriesAligner = "ALIGN_DELTA"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Backend request latency (p95)"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.labels.service_name=\"${var.backend_service_name}\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_DELTA"
                    crossSeriesReducer = "REDUCE_PERCENTILE_95"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Redis memory usage"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"redis.googleapis.com/stats/memory/usage_ratio\""
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_MEAN"
                  }
                }
              }
            }]
          }
        }
      ]
    }
  })
}
