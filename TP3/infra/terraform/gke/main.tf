resource "google_container_cluster" "tp3" {
  name                     = var.cluster_name
  location                 = var.zone
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = false
  networking_mode          = "VPC_NATIVE"
  ip_allocation_policy {}

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

# Nodegroup de infraestructura: RabbitMQ, Redis, Prometheus/Grafana.
# El taint evita que se agenden apps aca.
resource "google_container_node_pool" "infra" {
  name       = "infra"
  cluster    = google_container_cluster.tp3.id
  node_count = 1

  node_config {
    machine_type    = var.infra_machine_type
    spot            = var.spot
    service_account = var.nodes_service_account
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = { pool = "infra" }
    taint {
      key    = "pool"
      value  = "infra"
      effect = "NO_SCHEDULE"
    }
    workload_metadata_config { mode = "GKE_METADATA" }
  }
}

# Nodegroup de aplicaciones: frontend, backend, split, joiner, dlq-monitor.
resource "google_container_node_pool" "apps" {
  name    = "apps"
  cluster = google_container_cluster.tp3.id

  autoscaling {
    min_node_count = var.apps_min_nodes
    max_node_count = var.apps_max_nodes
  }

  node_config {
    machine_type    = var.apps_machine_type
    spot            = var.spot
    service_account = var.nodes_service_account
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = { pool = "apps" }
    workload_metadata_config { mode = "GKE_METADATA" }
  }
}
