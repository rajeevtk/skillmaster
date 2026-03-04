resource "google_service_account" "skillmaster" {
  account_id   = "${var.service_name}-sa"
  display_name = "Skill Master Service Account"
}

resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "${var.service_name}-anthropic-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret      = google_secret_manager_secret.anthropic_api_key.id
  secret_data = var.anthropic_api_key
}

resource "google_secret_manager_secret_iam_member" "anthropic_api_key_access" {
  secret_id = google_secret_manager_secret.anthropic_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.skillmaster.email}"
}

resource "google_secret_manager_secret" "neondb_url" {
  count     = var.neondb_url != "" ? 1 : 0
  secret_id = "${var.service_name}-neondb-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "neondb_url" {
  count       = var.neondb_url != "" ? 1 : 0
  secret      = google_secret_manager_secret.neondb_url[0].id
  secret_data = var.neondb_url
}

resource "google_secret_manager_secret_iam_member" "neondb_url_access" {
  count     = var.neondb_url != "" ? 1 : 0
  secret_id = google_secret_manager_secret.neondb_url[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.skillmaster.email}"
}
