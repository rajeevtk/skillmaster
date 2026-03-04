output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.skillmaster.uri
}

output "gcs_bucket" {
  description = "GCS bucket for skill storage"
  value       = google_storage_bucket.skills.name
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.skillmaster.email
}

output "artifact_registry" {
  description = "Artifact Registry repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.skillmaster.repository_id}"
}
