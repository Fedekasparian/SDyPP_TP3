# Pool de workers FUERA del cluster (Hit #2 y #3). Pipeline 2: .github/workflows/workers.yml
# terraform init -backend-config="bucket=<project_id>-tp3-tfstate"
terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.8" }
  }
  backend "gcs" {
    prefix = "workers"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
