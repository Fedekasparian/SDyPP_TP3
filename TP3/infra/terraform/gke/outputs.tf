output "cluster_name" {
  value = google_container_cluster.tp3.name
}

output "cluster_location" {
  value = google_container_cluster.tp3.location
}

output "get_credentials" {
  value = "gcloud container clusters get-credentials ${google_container_cluster.tp3.name} --zone ${google_container_cluster.tp3.location} --project ${var.project_id}"
}
