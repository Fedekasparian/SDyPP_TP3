locals {
  apis = [
    "container.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- Remote state (GCS tiene lock nativo) ----------
resource "google_storage_bucket" "tfstate" {
  name                        = "${var.project_id}-tp3-tfstate"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning { enabled = true }
}

# ---------- Registry PRIVADO (R1) ----------
resource "google_artifact_registry_repository" "tp3" {
  repository_id = "tp3"
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# ---------- Service accounts ----------
resource "google_service_account" "ci" {
  account_id   = "tp3-github-ci"
  display_name = "GitHub Actions (OIDC, sin claves)"
}

resource "google_service_account" "gke_nodes" {
  account_id   = "tp3-gke-nodes"
  display_name = "Nodos GKE"
}

resource "google_service_account" "workers" {
  account_id   = "tp3-workers"
  display_name = "VMs workers (fuera del cluster)"
}

resource "google_project_iam_member" "ci" {
  for_each = toset(var.ci_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_project_iam_member" "nodes" {
  for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter", "roles/monitoring.viewer", "roles/compute.viewer"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_project_iam_member" "workers" {
  for_each = toset(["roles/logging.logWriter", "roles/secretmanager.secretAccessor"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.workers.email}"
}

# Solo los nodos y los workers pueden BAJAR imagenes; nadie mas (evidencia R1).
resource "google_artifact_registry_repository_iam_member" "readers" {
  for_each   = { nodes = google_service_account.gke_nodes.email, workers = google_service_account.workers.email }
  location   = google_artifact_registry_repository.tp3.location
  repository = google_artifact_registry_repository.tp3.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${each.value}"
}

# ---------- Workload Identity Federation para GitHub Actions (OIDC) ----------
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == \"${var.github_repo}\""
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# ---------- Secret Manager (los VALORES se cargan a mano o por pipeline, nunca en el repo) ----------
resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(["tp3-rabbit-pass", "tp3-redis-pass", "tp3-auth-secret"])
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}
