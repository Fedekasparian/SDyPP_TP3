variable "project_id" {
  type        = string
  description = "ID del proyecto GCP"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "github_repo" {
  type        = string
  description = "owner/repo autorizado a autenticarse via OIDC"
  default     = "Fedekasparian/SDyPP_TP3"
}

variable "ci_roles" {
  type        = list(string)
  description = "Roles del service account que usa GitHub Actions"
  default = [
    "roles/container.admin",
    "roles/artifactregistry.writer",
    "roles/compute.admin",
    "roles/iam.serviceAccountUser",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
  ]
}
