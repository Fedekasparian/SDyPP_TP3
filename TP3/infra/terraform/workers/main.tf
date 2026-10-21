# Ciclo de cada worker: provisioning (VM) -> bootstrap (startup-script = user_data)
# -> deploy (pull de la imagen del registry privado) -> join (se conecta a RabbitMQ)
# -> teardown (worker_count=0 o terraform destroy).
#
# Sin claves estaticas: la VM corre con el SA `tp3-workers`; Docker se autentica al
# Artifact Registry y lee las contraseñas de Secret Manager usando el token del
# metadata server.

resource "google_compute_instance" "worker" {
  count        = var.worker_count
  name         = "tp3-worker-${count.index}"
  machine_type = var.machine_type
  zone         = var.zones[count.index % length(var.zones)]
  tags         = ["tp3-worker"]
  labels       = { app = "tp3-worker", pool = var.worker_pool }

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network = "default"
    access_config {} # IP publica efimera para salir a internet (apt, registry)
  }

  scheduling {
    preemptible                 = var.spot
    automatic_restart           = !var.spot
    provisioning_model          = var.spot ? "SPOT" : "STANDARD"
    instance_termination_action = var.spot ? "DELETE" : null
  }

  service_account {
    email  = var.workers_service_account
    scopes = ["cloud-platform"]
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tftpl", {
      region       = var.region
      worker_image = var.worker_image
      worker_pool  = var.worker_pool
      rabbit_host  = var.rabbit_host
      redis_host   = var.redis_host
    })
  }
}

# Prometheus (dentro del VPC) scrapea /metrics y /health de los workers.
resource "google_compute_firewall" "worker_metrics" {
  name          = "tp3-worker-metrics"
  network       = "default"
  source_ranges = ["10.0.0.0/8"]
  target_tags   = ["tp3-worker"]
  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}
