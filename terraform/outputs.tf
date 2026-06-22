output "backend_url" {
  description = "Public URL of the backend Cloud Run service"
  value       = module.cloud_run.backend_url
}

output "worker_url" {
  description = "Internal URL of the worker Cloud Run service"
  value       = module.cloud_run.worker_url
}

output "redis_host" {
  description = "Redis host"
  value       = module.redis.host
}

output "artifact_registry_url" {
  description = "Artifact Registry URL for pushing images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}"
}

output "workload_identity_provider" {
  description = "Workload Identity Provider resource name — paste into GitHub Actions repo variable WIF_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}
