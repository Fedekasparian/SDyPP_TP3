# Hit #2: Sobel con offloading en la nube

**Responsable: Integrante C**

Workers bajo demanda con Terraform: [TP3/infra/terraform/workers](../infra/terraform/workers/).

| Paso | Cómo |
|---|---|
| Provisioning | `google_compute_instance` con `count = var.worker_count`, repartidas en varias zonas por las cuotas |
| Bootstrap | `startup-script` (equivalente a `user_data`) instala Docker: [startup.sh.tftpl](../infra/terraform/workers/startup.sh.tftpl) |
| Deploy | `docker pull` del Artifact Registry privado con el SA de la VM (sin claves) |
| Join | `docker run` del worker. Se conecta a RabbitMQ y Redis con retry y backoff |
| Teardown | `worker_count=0` o `terraform destroy` (pipeline `workers.yml`) |

Requisitos IaC: remote state en GCS (con lock nativo), archivos `provider/variables/main/outputs.tf`, plan en cada PR y apply manual o al mergear.

## Arquitectura híbrida (tipo 1)
TODO (C): diagrama y tabla.

| Servicio | ¿Local o nube? | Por qué |
|---|---|---|
| frontend / backend | | |
| RabbitMQ / Redis | | |
| split / joiner | | |
| workers | nube | Es el cómputo elástico: se crea solo cuando la demanda supera la capacidad local (offloading / cloud-bursting) |

> En el modo híbrido, las VMs tienen que llegar al RabbitMQ y al Redis **locales**. Las opciones son exponerlos con TLS y credenciales fuertes, usar un túnel (Tailscale, WireGuard, Cloudflare Tunnel) o una VPN. Pasar la IP con `-var rabbit_host=... -var redis_host=...`.

## Cómo correr
```bash
cd TP3/infra/terraform/workers
terraform init -backend-config="bucket=<project>-tp3-tfstate"
terraform apply -var project_id=... -var workers_service_account=... \
  -var worker_image=us-central1-docker.pkg.dev/<p>/tp3/worker:latest \
  -var rabbit_host=<ip> -var redis_host=<ip> -var worker_count=2
terraform apply ... -var worker_count=0   # teardown
```
