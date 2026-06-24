# production/terraform.tfvars — fill in before running terraform apply

project_id    = "your-gcp-project-id"
region        = "us-central1"
environment   = "production"
artifact_repo = "y2d"

backend_image = "us-central1-docker.pkg.dev/your-gcp-project-id/y2d/backend:latest"
worker_image  = "us-central1-docker.pkg.dev/your-gcp-project-id/y2d/worker:latest"

google_client_id     = "your-client-id.apps.googleusercontent.com"
google_client_secret = "your-client-secret"

alert_email     = "you@example.com"
redis_memory_gb = 2
