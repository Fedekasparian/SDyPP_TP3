# Bootstrap: se corre UNA vez a mano (crea el bucket del remote state, el registry,
# las service accounts y la federacion OIDC para GitHub Actions).
#
#   terraform init && terraform apply -var project_id=<id>
#   # Despues de crear el bucket, migrar este mismo state al bucket:
#   #   descomentar el backend "gcs" de abajo y correr:
#   terraform init -migrate-state -backend-config="bucket=<project_id>-tp3-tfstate"
terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.8" }
  }
  # backend "gcs" {
  #   prefix = "bootstrap"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
