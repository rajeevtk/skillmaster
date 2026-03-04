variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run and GCS"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "skillmaster"
}

variable "gcs_bucket_name" {
  description = "GCS bucket for storing generated skills"
  type        = string
  default     = "skillmaster-skills"
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "anthropic_api_key" {
  description = "Anthropic API key (stored as Cloud Run secret)"
  type        = string
  sensitive   = true
}

variable "neondb_url" {
  description = "NeonDB connection string (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 10
}

variable "min_instances" {
  description = "Minimum Cloud Run instances (0 = scale to zero)"
  type        = number
  default     = 0
}
