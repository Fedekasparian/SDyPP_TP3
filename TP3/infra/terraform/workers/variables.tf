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

variable "blob_bucket" {
  type        = string
  description = "Bucket de imagenes (output images_bucket del bootstrap). En Redis solo va el puntero"
  default     = ""
}

variable "spot" {
  type    = bool
  default = true
}

# false: la VM sale a internet por el Cloud NAT `tp3-nat` (lo crea gke_up.sh) y no consume
# IP publica. La cuota regional es de 8 IPs y los nodos de GKE ya usan varias: con V3=6 no entran.
variable "external_ip" {
  type    = bool
  default = true
}

# --- Modo hibrido (Hit #2): la VM llega a la RabbitMQ/Redis de un equipo local por Tailscale ---
variable "name_prefix" {
  type        = string
  description = "Prefijo del nombre y label app de las VMs (tp3-worker en el Hit #3, tp3-hibrido en el Hit #2)"
  default     = "tp3-worker"
}

variable "rabbit_pass_secret" {
  type    = string
  default = "tp3-rabbit-pass"
}

variable "redis_pass_secret" {
  type    = string
  default = "tp3-redis-pass"
}

variable "tailscale_authkey_secret" {
  type        = string
  description = "Secreto con la auth key de Tailscale. Vacio = sin Tailscale (Hit #3, ILB interno)"
  default     = ""
}

variable "create_firewall" {
  type        = bool
  description = "La regla de firewall de metricas la crea solo el estado del Hit #3"
  default     = true
}
