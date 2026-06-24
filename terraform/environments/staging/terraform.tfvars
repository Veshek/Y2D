# staging/terraform.tfvars — fill in before running terraform apply

project_id    = "your-gcp-project-id"
region        = "us-central1"
environment   = "staging"
artifact_repo = "y2d"

# These are set after first docker build + push via CI
backend_image = "us-central1-docker.pkg.dev/your-gcp-project-id/y2d/backend:latest"
worker_image  = "us-central1-docker.pkg.dev/your-gcp-project-id/y2d/worker:latest"

# OAuth credentials (from Google Cloud Console)
google_client_id     = "your-client-id.apps.googleusercontent.com"
google_client_secret = "your-client-secret"

alert_email   = "you@example.com"
redis_memory_gb = 1
