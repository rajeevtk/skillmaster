resource "google_storage_bucket" "skills" {
  name                        = var.gcs_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "service_account_write" {
  bucket = google_storage_bucket.skills.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.skillmaster.email}"
}
