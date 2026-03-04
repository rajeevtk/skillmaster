resource "google_artifact_registry_repository" "skillmaster" {
  location      = var.region
  repository_id = var.service_name
  format        = "DOCKER"
  depends_on    = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

locals {
  image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.skillmaster.repository_id}/${var.service_name}:${var.image_tag}"
}

resource "google_cloud_run_v2_service" "skillmaster" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.skillmaster.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = local.image_uri

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "SKILLMASTER_GCS_BUCKET"
        value = google_storage_bucket.skills.name
      }

      env {
        name  = "SKILLMASTER_GCS_PROJECT"
        value = var.project_id
      }

      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = var.neondb_url != "" ? [1] : []
        content {
          name = "NEONDB_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.neondb_url[0].secret_id
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_secret_manager_secret_version.anthropic_api_key,
  ]
}

# Allow unauthenticated access (configure as needed)
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.skillmaster.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
