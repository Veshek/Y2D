terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  # Remote state — create a GCS bucket named "${project_id}-tfstate" before init.
  backend "gcs" {
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Enable required APIs ---------------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudtasks.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# --- Artifact Registry ------------------------------------------------------
resource "google_artifact_registry_repository" "y2d" {
  repository_id = var.artifact_repo
  format        = "DOCKER"
  location      = var.region
  description   = "Y2D container images"
  depends_on    = [google_project_service.apis]
}

# --- Secrets ----------------------------------------------------------------
resource "google_secret_manager_secret" "google_client_id" {
  secret_id = "y2d-google-client-id-${var.environment}"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "google_client_id" {
  secret      = google_secret_manager_secret.google_client_id.id
  secret_data = var.google_client_id
}

resource "google_secret_manager_secret" "google_client_secret" {
  secret_id = "y2d-google-client-secret-${var.environment}"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "google_client_secret" {
  secret      = google_secret_manager_secret.google_client_secret.id
  secret_data = var.google_client_secret
}

# --- Service accounts -------------------------------------------------------
resource "google_service_account" "backend" {
  account_id   = "y2d-backend-${var.environment}"
  display_name = "Y2D Backend (${var.environment})"
}

resource "google_service_account" "worker" {
  account_id   = "y2d-worker-${var.environment}"
  display_name = "Y2D Worker (${var.environment})"
}

# SA that Cloud Tasks uses to call the private worker
resource "google_service_account" "tasks_invoker" {
  account_id   = "y2d-tasks-invoker-${var.environment}"
  display_name = "Y2D Tasks Invoker (${var.environment})"
}

# --- Modules ----------------------------------------------------------------
module "redis" {
  source        = "./modules/redis"
  project_id    = var.project_id
  region        = var.region
  environment   = var.environment
  memory_gb     = var.redis_memory_gb
  depends_on    = [google_project_service.apis]
}

module "queue" {
  source       = "./modules/queue"
  project_id   = var.project_id
  region       = var.region
  environment  = var.environment
  worker_url   = module.cloud_run.worker_url
  invoker_sa   = google_service_account.tasks_invoker.email
  depends_on   = [google_project_service.apis]
}

module "cloud_run" {
  source               = "./modules/cloud_run"
  project_id           = var.project_id
  region               = var.region
  environment          = var.environment
  backend_image        = var.backend_image
  worker_image         = var.worker_image
  backend_sa_email     = google_service_account.backend.email
  worker_sa_email      = google_service_account.worker.email
  tasks_invoker_sa     = google_service_account.tasks_invoker.email
  redis_host           = module.redis.host
  redis_port           = module.redis.port
  queue_name           = module.queue.queue_name
  google_client_id_secret     = google_secret_manager_secret.google_client_id.id
  google_client_secret_secret = google_secret_manager_secret.google_client_secret.id
  depends_on           = [google_project_service.apis]
}

module "monitoring" {
  source        = "./modules/monitoring"
  project_id    = var.project_id
  environment   = var.environment
  alert_email   = var.alert_email
  backend_service_name = "y2d-backend-${var.environment}"
  worker_service_name  = "y2d-worker-${var.environment}"
  queue_name           = module.queue.queue_name
  depends_on    = [google_project_service.apis]
}

# --- IAM: allow backend to use Secret Manager -------------------------------
resource "google_secret_manager_secret_iam_member" "backend_client_id" {
  secret_id = google_secret_manager_secret.google_client_id.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_secret_manager_secret_iam_member" "backend_client_secret" {
  secret_id = google_secret_manager_secret.google_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

# --- IAM: allow tasks invoker to call the private worker --------------------
resource "google_cloud_run_v2_service_iam_member" "tasks_invoker" {
  project  = var.project_id
  location = var.region
  name     = "y2d-worker-${var.environment}"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tasks_invoker.email}"
  depends_on = [module.cloud_run]
}

# --- Workload Identity Federation for GitHub Actions ------------------------
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}
