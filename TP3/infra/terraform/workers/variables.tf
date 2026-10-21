variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zones" {
  type        = list(string)
  description = "Las cuotas free limitan VMs por zona/region: se reparten entre varias"
  default     = ["us-central1-a", "us-central1-b", "us-central1-c"]
}

variable "worker_count" {
  type        = number
  description = "Cantidad de VMs workers. 0 = teardown"
  default     = 0
}

variable "machine_type" {
  type    = string
  default = "e2-small"
}

variable "workers_service_account" {
  type        = string
  description = "Email del SA de workers (output del bootstrap)"
}

variable "worker_image" {
  type        = string
  description = "Imagen del worker en el registry privado, ej: us-central1-docker.pkg.dev/<p>/tp3/worker:<sha>"
}

variable "worker_pool" {
  type        = string
  description = "Pool/cola que atienden estas VMs (debe estar en ALLOWED_WORKER_IMAGES)"
  default     = "tp3-worker"
}

variable "rabbit_host" {
  type        = string
  description = "IP del LoadBalancer interno de RabbitMQ en GKE (o IP publica en el modo hibrido del Hit #2)"
}

variable "redis_host" {
  type        = string
  description = "IP del LoadBalancer interno de Redis"
}

variable "spot" {
  type    = bool
  default = true
}
