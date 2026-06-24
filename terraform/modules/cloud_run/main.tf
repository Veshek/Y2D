variable "project_id" {}
variable "region" {}
variable "environment" {}
variable "backend_image" {}
variable "worker_image" {}
variable "backend_sa_email" {}
variable "worker_sa_email" {}
variable "tasks_invoker_sa" {}
variable "redis_host" {}
variable "redis_port" {}
variable "queue_name" {}
variable "google_client_id_secret" {}
variable "google_client_secret_secret" {}

locals {
  redis_url = "redis://${var.redis_host}:${var.redis_port}/0"
}

# --- Backend (public) -------------------------------------------------------
resource "google_cloud_run_v2_service" "backend" {
  name     = "y2d-backend-${var.environment}"
  location = var.region

  template {
    service_account = var.backend_sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = var.backend_image

      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }

      env {
        name  = "REDIS_URL"
        value = local.redis_url
      }
      env {
        name  = "QUEUE_BACKEND"
        value = "cloud_tasks"
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.region
      }
      env {
        name  = "QUEUE_NAME"
        value = var.queue_name
      }
      env {
        name  = "WORKER_INVOKER_SA"
        value = var.tasks_invoker_sa
      }
      env {
        name = "GOOGLE_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = var.google_client_id_secret
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.google_client_secret_secret
            version = "latest"
          }
        }
      }

      liveness_probe {
        http_get { path = "/healthz" }
        initial_delay_seconds = 10
        period_seconds        = 30
      }
    }
  }
}

# Make backend publicly accessible
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Worker (private — Cloud Tasks only) ------------------------------------
resource "google_cloud_run_v2_service" "worker" {
  name     = "y2d-worker-${var.environment}"
  location = var.region

  template {
    service_account = var.worker_sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 20
    }

    # Workers need more resources for video processing
    containers {
      image = var.worker_image

      resources {
        limits = { cpu = "2", memory = "2Gi" }
        # Keep CPU allocated during transfer (don't throttle between chunks)
        cpu_idle = false
      }

      env {
        name  = "REDIS_URL"
        value = local.redis_url
      }

      # Allow up to 15 min for large video transfers
      timeout = "900s"

      liveness_probe {
        http_get { path = "/healthz" }
        initial_delay_seconds = 10
        period_seconds        = 30
      }
    }
  }
}

output "backend_url" { value = google_cloud_run_v2_service.backend.uri }
output "worker_url"  { value = google_cloud_run_v2_service.worker.uri }
