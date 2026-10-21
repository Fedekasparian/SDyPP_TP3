variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type        = string
  description = "Cluster zonal: mas barato y alcanza para el TP"
  default     = "us-central1-a"
}

variable "cluster_name" {
  type    = string
  default = "tp3"
}

variable "nodes_service_account" {
  type        = string
  description = "Email del SA de nodos (output del bootstrap)"
}

variable "infra_machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "apps_machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "apps_min_nodes" {
  type    = number
  default = 1
}

variable "apps_max_nodes" {
  type    = number
  default = 3
}

variable "spot" {
  type        = bool
  description = "Nodos spot para ahorrar creditos"
  default     = true
}
