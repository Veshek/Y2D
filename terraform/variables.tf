variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (staging or production)"
  type        = string
}

variable "artifact_repo" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "y2d"
}

variable "backend_image" {
  description = "Full backend container image URI"
  type        = string
}

variable "worker_image" {
  description = "Full worker container image URI"
  type        = string
}

variable "google_client_id" {
  description = "Google OAuth client ID"
  type        = string
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth client secret"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
}

variable "redis_memory_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}
