variable "project_id" {}
variable "region" {}
variable "environment" {}
variable "worker_url" {}
variable "invoker_sa" {}

resource "google_cloud_tasks_queue" "transfers" {
  name     = "clipflow-transfers-${var.environment}"
  location = var.region

  rate_limits {
    # Max concurrent transfers — keeps worker instances manageable
    max_concurrent_dispatches = 20
    max_dispatches_per_second = 5
  }

  retry_config {
    max_attempts       = 3
    max_retry_duration = "3600s"  # give up after 1 hour total
    min_backoff        = "30s"
    max_backoff        = "300s"
    max_doublings      = 3
  }

  # Purge tasks that haven't been processed after 24 hours
  stackdriver_logging_config {
    sampling_ratio = 1.0  # log all task dispatches
  }
}

output "queue_name" { value = google_cloud_tasks_queue.transfers.name }
output "queue_path" {
  value = "projects/${var.project_id}/locations/${var.region}/queues/clipflow-transfers-${var.environment}"
}
