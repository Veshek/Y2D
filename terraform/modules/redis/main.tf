variable "project_id" {}
variable "region" {}
variable "environment" {}
variable "memory_gb" { default = 1 }

resource "google_redis_instance" "main" {
  name           = "clipflow-redis-${var.environment}"
  tier           = "BASIC"
  memory_size_gb = var.memory_gb
  region         = var.region

  redis_version  = "REDIS_7_0"
  display_name   = "Clipflow Redis (${var.environment})"

  # Enable AUTH for production security
  auth_enabled = true

  redis_configs = {
    # Evict least-recently-used keys when memory is full
    # (progress events are ephemeral — losing old ones is acceptable)
    "maxmemory-policy" = "allkeys-lru"
  }
}

output "host" { value = google_redis_instance.main.host }
output "port" { value = google_redis_instance.main.port }
output "auth_string" {
  value     = google_redis_instance.main.auth_string
  sensitive = true
}
