# Arquitectura

## Flujo de un job

```mermaid
flowchart LR
  U[Usuario / k6] -->|POST /jobs + Bearer| FE[frontend nginx]
  FE -->|/api| BE[backend x3<br/>FastAPI stateless]
  BE -- valida R2 --> BE
  BE -->|archivos| B[(Bucket GCS<br/>imágenes)]
  BE -->|estado + punteros gs://| R[(Redis)]
  BE -->|job_id| QS[[split.requests]]
  QS --> SP[split]
  SP -->|fragmentos| B
  SP -->|punteros| R
  SP -->|1 msg por fragmento<br/>exchange tasks, rk=worker_image| QT[[tasks.tp3-worker<br/>quorum, delivery-limit]]
  QT --> W1[worker]
  QT --> W2[worker]
  QT --> W3[worker ...]
  W1 & W2 & W3 -->|fragmento procesado| B
  W1 & W2 & W3 -->|puntero| R
  W1 & W2 & W3 -->|fanout results| QJ[[results.joiner]]
  W1 & W2 & W3 -->|fanout results| QM[[results.monitor]]
  QJ --> J[joiner] -->|imagen final| B
  J -->|puntero + done| R
  QT -. nack / delivery-limit .-> DLX{{tasks.dlx}} --> DLQ[[tasks.dlq]]
  DLQ --> M[dlq-monitor]
  QM --> M
  M -->|stream de progreso con TTL| R
  R -->|snapshot y eventos| BE
  BE -->|SSE autorizado| FE
  M -->|attempt+1| QT
  M -->|agotó reintentos| P[[tasks.parked]]
  P -->|POST /admin/dlq/reprocess| QT
```

## Despliegue en GKE (Hit #3)

```mermaid
flowchart TB
  subgraph GCP[Proyecto GCP]
    AR[(Artifact Registry<br/>privado)]
    SM[(Secret Manager)]
    GCS[(GCS: remote state)]
    IMG[(GCS: bucket de imágenes<br/>lifecycle 1 día)]
    subgraph GKE[Cluster GKE]
      subgraph infra[nodepool infra - taint pool=infra]
        RMQ[RabbitMQ] 
        RED[Redis]
        PROM[Prometheus + Grafana + Alertmanager]
      end
      subgraph apps[nodepool apps]
        FE2[frontend] --> BE2[backend x3]
        SP2[split x2]
        JO2[joiner x2]
        DM2[dlq-monitor]
      end
      ILB[LB interno RabbitMQ/Redis]
    end
    subgraph VMs[Pool de workers - VMs Terraform, fuera del cluster]
      V1[tp3-worker-0]
      V2[tp3-worker-1]
      V3[tp3-worker-N]
    end
  end
  GH[GitHub Actions<br/>OIDC, sin claves] -->|push imágenes| AR
  GH -->|terraform| GKE
  GH -->|terraform| VMs
  AR -->|pull con SA de nodos| GKE
  AR -->|pull con SA tp3-workers| VMs
  SM -->|contraseñas| VMs
  V1 & V2 & V3 --> ILB --> RMQ & RED
  V1 & V2 & V3 -->|SA tp3-workers| IMG
  apps -->|Workload Identity, KSA tp3-apps| IMG
  Internet -->|Ingress público| FE2
```

## Decisiones de diseño
- **Imágenes en un bucket, punteros en Redis**: por el broker solo viajan mensajes chicos (JSON con el puntero `gs://...` del fragmento) y los bytes van a un bucket de GCS (`<proyecto>-tp3-images`). Redis guarda únicamente estado y punteros (~80 bytes por clave). Antes los bytes iban a Redis y la memoria crecía con el tamaño de los archivos: con carga sostenida el pod terminó `OOMKilled` (sección 8.7 del informe). Con el bucket, la memoria de Redis depende de la cantidad de jobs y no de su tamaño, y el `maxmemory 1200mb` sobra. Una regla de lifecycle borra los objetos al día, igual que el TTL de 24 h del job. Los pods autentican con Workload Identity (KSA `tp3-apps`) y las VMs con su SA, sin claves. En local (`docker compose`, overlay `local`) el bucket es el emulador `fake-gcs-server`, con el mismo cliente y los mismos punteros. El código está en `tp3common/blobs.py`.
- **Solapamiento al partir**: cada operación 3×3 necesita 1 px de vecinos, así que una cadena de k operaciones necesita k px. Sin ese solapamiento aparecen líneas en las uniones. Lo verifica `test_split_process_join_equals_full_image`.
- **Sin normalización por el máximo** en Sobel (se recorta a 255). Si cada fragmento normalizara por su propio máximo, los fragmentos no quedarían consistentes entre sí.
- **Idempotencia del joiner**: `SADD` de `fragment_id` y `SET NX` del lock de armado. Los resultados duplicados por reentregas no rompen nada y con varias réplicas del joiner solo una arma la imagen.
- **404 en lugar de 403** cuando un usuario consulta un job ajeno, para no revelar que el job existe.
- El diagrama de la arquitectura híbrida del Hit #2, con la justificación local o nube de cada servicio, está en [hit2/README.md](../hit2/README.md).
