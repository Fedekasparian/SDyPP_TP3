# Ciclo de cada worker: provisioning (VM) -> bootstrap (startup-script = user_data)
# -> deploy (pull de la imagen del registry privado) -> join (se conecta a RabbitMQ)
# -> teardown (worker_count=0 o terraform destroy).
#
# Sin claves estaticas: la VM corre con el SA `tp3-workers`; Docker se autentica al
# Artifact Registry y lee las contraseñas de Secret Manager usando el token del
# metadata server.

resource "google_compute_instance" "worker" {
  count        = var.worker_count
  name         = "${var.name_prefix}-${count.index}"
  machine_type = var.machine_type
  zone         = var.zones[count.index % length(var.zones)]
  tags         = ["tp3-worker"]
  labels       = { app = var.name_prefix, pool = var.worker_pool }

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network = "default"
    # IP publica efimera para salir a internet (apt, registry). Sin ella, sale por Cloud NAT.
    dynamic "access_config" {
      for_each = var.external_ip ? [1] : []
      content {}
    }
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
      region           = var.region
      worker_image     = var.worker_image
      worker_pool      = var.worker_pool
      rabbit_host      = var.rabbit_host
      redis_host       = var.redis_host
      blob_bucket      = var.blob_bucket
      rabbit_secret    = var.rabbit_pass_secret
      redis_secret     = var.redis_pass_secret
      tailscale_secret = var.tailscale_authkey_secret
    })
  }
}

# Prometheus (dentro del VPC) scrapea /metrics y /health de los workers.
moved {
  from = google_compute_firewall.worker_metrics
  to   = google_compute_firewall.worker_metrics[0]
}

resource "google_compute_firewall" "worker_metrics" {
  count         = var.create_firewall ? 1 : 0
  name          = "tp3-worker-metrics"
  network       = "default"
  source_ranges = ["10.0.0.0/8"]
  target_tags   = ["tp3-worker"]
  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}
