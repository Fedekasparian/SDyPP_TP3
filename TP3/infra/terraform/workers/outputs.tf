output "worker_names" {
  value = google_compute_instance.worker[*].name
}

output "worker_internal_ips" {
  value = google_compute_instance.worker[*].network_interface[0].network_ip
}
