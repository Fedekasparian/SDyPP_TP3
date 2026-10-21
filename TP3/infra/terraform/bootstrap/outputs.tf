# Cargar estos valores como GitHub *Variables* (no son secretos):
#   GCP_PROJECT, GCP_REGION, GCP_WIF_PROVIDER, GCP_CI_SA, TF_STATE_BUCKET,
#   GKE_NODES_SA, WORKERS_SA
output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "ci_service_account" {
  value = google_service_account.ci.email
}

output "gke_nodes_service_account" {
  value = google_service_account.gke_nodes.email
}

output "workers_service_account" {
  value = google_service_account.workers.email
}

output "tfstate_bucket" {
  value = google_storage_bucket.tfstate.name
}

output "registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.tp3.repository_id}"
}
