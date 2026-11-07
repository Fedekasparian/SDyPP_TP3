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

## Arquitectura híbrida (tipo 1): local + cloud-bursting

La consigna pide un esquema **híbrido**: parte de la aplicación corre en equipos locales
(on-premise) y el cómputo intensivo se "desborda" a la nube (cloud-bursting). Los workers
de Sobel son las únicas piezas que se crean y destruyen on-demand en GCP con Terraform.

```mermaid
flowchart LR
  subgraph LOCAL["Local (k3d / k3s en mi equipo)"]
    Client[Cliente] --> Frontend[Frontend]
    Frontend --> Backend[Backend]
    Backend --> RabbitMQ[(RabbitMQ)]
    Backend <--> Redis[(Redis)]
    RabbitMQ --> Split[Split]
    Split <--> Redis
    RabbitMQ --> Joiner[Joiner]
    Joiner <--> Redis
    RabbitMQ --> LocalW[Workers locales<br/>capacidad base]
  end
  subgraph GCP["Google Cloud (Terraform)"]
    VMs[Workers: VMs spot<br/>0..N, bajo demanda]
    AR[(Artifact Registry<br/>privado)]
    SM[(Secret Manager)]
  end
  RabbitMQ -. "túnel / VPN (AMQP 5672)" .-> VMs
  Redis -. "túnel / VPN (6379, con password)" .-> VMs
  AR -->|pull con SA, sin claves| VMs
  SM -->|passwords| VMs
```

| Servicio | ¿Local o nube? | Por qué |
|---|---|---|
| frontend / backend | Local | Es la entrada de la aplicación; no es cómputo intensivo y no justifica pagar nube. |
| split / joiner | Local | Operan sobre metadatos y fragmentos pequeños, cerca de RabbitMQ y Redis (baja latencia). |
| RabbitMQ / Redis | Local | Son el punto de coordinación; si estuvieran en la nube, cada mensaje local cruzaría Internet. |
| workers base | Local | Capacidad propia (costo fijo ya pagado). |
| workers extra | **Nube (VMs spot)** | Cómputo elástico: se crean al saturarse la capacidad local y se destruyen al terminar (`worker_count=0`). Se paga solo por el tiempo de uso. |
| imágenes y secretos | Nube (Artifact Registry, Secret Manager) | Registry privado (R1) y credenciales sin claves estáticas en las VMs. |

**Cómo llegan las VMs a la RabbitMQ/Redis locales.** Es el punto delicado del esquema híbrido:
las VMs necesitan una ruta de red hacia tu equipo. Opciones, de más a menos recomendable:
VPN/overlay (Tailscale, WireGuard), túnel TCP (cloudflared, ngrok) o IP pública con port-forward
restringido por firewall. En todos los casos se pasa esa dirección como `rabbit_host` / `redis_host`.
No exponer Redis sin password (el Deployment de Redis del overlay local no la tiene: agregar
`--requirepass` antes de abrirlo) ni dejar AMQP abierto a todo Internet.

**Validado el 07/11/2026** con Tailscale: la VM `tp3-hibrido-0` (GCP, `us-central1-a`) consumió de
la RabbitMQ local y escribió en la Redis local de un equipo Windows con Docker Desktop. Cada
escenario procesa 6 jobs concurrentes × 5 imágenes de 1 MB × 4 fragmentos (`sobel`). Evidencia en
[evidencia/hit2/](../evidencia/hit2/):

| Escenario | Workers | Jobs | Lote completo | p50 por job | max por job |
|---|---|---|---|---|---|
| [local](../evidencia/hit2/local.txt) | 2 locales | 6/6 | 2,50 s | 1,96 s | 2,45 s |
| [nube](../evidencia/hit2/nube.txt) | solo la VM | 6/6 | 197,60 s | 117,07 s | 197,52 s |
| [mixto](../evidencia/hit2/mixto.txt) | 2 locales + VM | 6/6 | 2,91 s | 1,79 s | 2,83 s |

La columna `workers` de cada archivo muestra qué worker tocó cada job (`tp3-hibrido-0` = la VM).
En `nube`, el procesamiento de un job tarda ~30 s contra ~0,25 s en local: cada fragmento de 1 MB
va y vuelve por Internet entre la Redis local y la VM, así que el costo es de red y no de CPU. El
cloud-bursting conviene para operaciones con mucho cómputo por byte; para Sobel sobre imágenes
chicas, la latencia de la red domina. En `mixto` la VM participó en 1 de los 6 jobs: los workers
locales vacían la cola antes de que la VM termine sus fragmentos.

> Docker Desktop hace NAT del puerto publicado, así que en la lista de conexiones AMQP la VM
> aparece como `172.20.0.1` (el gateway de Docker) y no con su IP `100.x`. Lo que la identifica es
> el `worker_id` `tp3-hibrido-0` y la quinta conexión en el escenario `nube`, donde no hay
> workers locales.

## Qué cambia en el Hit #3 (100% nube)

En el Hit #3 todo corre en GKE (RabbitMQ y Redis en el nodepool `infra`; frontend, backend,
split, joiner y dlq-monitor en `apps`) y solo los workers quedan en VMs fuera del cluster. Las VMs
alcanzan RabbitMQ/Redis por los `LoadBalancer` internos del VPC, sin exponerlos a Internet.
Ver [hit3/README.md](../hit3/README.md) y [infra/README.md](../infra/README.md).

| Servicio | Hit #2 (híbrido) | Hit #3 (cloud native) |
|---|---|---|
| frontend, backend, split, joiner | Local | GKE, pool `apps` |
| RabbitMQ, Redis | Local | GKE, pool `infra` |
| workers | Local + VMs en la nube | VMs en la nube (fuera del cluster) |

> En un cluster RabbitMQ, las quorum queues priorizan consistencia (CP): ante una partición, la
> minoría deja de aceptar escrituras. Redis con replicación asíncrona prioriza disponibilidad (AP):
> puede servir lecturas atrasadas o perder escrituras recientes al hacer failover. Los manifiestos
> actuales despliegan una sola réplica de cada uno, por lo que no ofrecen alta disponibilidad.

## Cómo correr
```bash
cd TP3/infra/terraform/workers
terraform init -backend-config="bucket=<project>-tp3-tfstate"
terraform apply -var project_id=... -var workers_service_account=... \
  -var worker_image=us-central1-docker.pkg.dev/<p>/tp3/worker:latest \
  -var rabbit_host=<ip> -var redis_host=<ip> -var worker_count=2
terraform apply ... -var worker_count=0   # teardown
```

## Corrida híbrida

La VM de GCP llega a la RabbitMQ y la Redis del equipo local por **Tailscale**. El workflow
[hibrido.yml](../../.github/workflows/hibrido.yml) usa un estado de Terraform propio
(`prefix=workers-hibrido`), así que no toca las VMs del Hit #3. Los secretos están en Secret Manager:
`tp3-tailscale-authkey`, `tp3-hibrido-rabbit-pass` y `tp3-hibrido-redis-pass`.

1. En el equipo local: Tailscale conectado al mismo tailnet y anotar la IP (`tailscale ip -4`, una `100.x`).
2. `.env` con `RABBIT_PASS` y `REDIS_PASS` iguales a los secretos `tp3-hibrido-*`, y levantar el stack:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.hibrido.yml up -d --build --scale worker=2
   ```
3. Crear la VM: `gh workflow run hibrido.yml -f worker_count=1 -f local_host=<ip 100.x>`. El log
   muestra el `tailscale ping` desde la VM.
4. Medir los tres escenarios (cada uno deja `TP3/evidencia/hit2/<escenario>.txt`):
   ```bash
   py TP3/scripts/hibrido_evidencia.py local      # sin VM
   docker compose up -d --no-deps --scale worker=0 worker
   py TP3/scripts/hibrido_evidencia.py nube       # solo la VM
   docker compose up -d --no-deps --scale worker=2 worker
   py TP3/scripts/hibrido_evidencia.py mixto      # locales + VM (cloud-bursting)
   ```
5. Teardown: `gh workflow run hibrido.yml -f worker_count=0`.

## Kubernetes local

El cluster local es **k3d** (Windows/macOS) o **k3s** (Linux/WSL2), según la Práctica 0 de la cátedra
(Minikube también funciona). Con Docker, `kubectl` y el cluster elegido instalados, crear `.env`
desde `.env.example` con credenciales locales y ejecutar desde Git Bash o WSL:

```bash
bash TP3/scripts/local_up.sh            # detecta k3d / k3s / minikube
CLUSTER=minikube bash TP3/scripts/local_up.sh   # forzar uno
```

El script crea el cluster, construye las imágenes, las importa (`k3d image import`,
`k3s ctr images import` o `minikube image load`), crea los Secrets del namespace `tp3` a partir del
`.env` y aplica `TP3/k8s/overlays/local`. No usa GCP.

## Evidencia R1

Para probar el acceso al registry privado desde el cluster local, autenticar `gcloud` con
permisos de lectura en Artifact Registry y ejecutar:

```bash
R1_IMAGE=us-central1-docker.pkg.dev/<project>/tp3/backend:<tag> \
  bash TP3/scripts/r1_evidence.sh
```

El script documenta primero `ImagePullBackOff` sin credenciales y luego el mismo
Deployment funcionando con un `imagePullSecret` temporal. La salida se guarda en
`TP3/evidencia/r1/`; no subir tokens ni credenciales al repositorio.
