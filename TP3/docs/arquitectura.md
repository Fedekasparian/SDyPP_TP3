# Arquitectura

## Flujo de un job

```mermaid
flowchart LR
  U[Usuario / k6] -->|POST /jobs + Bearer| FE[frontend nginx]
  FE -->|/api| BE[backend x3<br/>FastAPI stateless]
  BE -- valida R2 --> BE
  BE -->|archivos + estado| R[(Redis)]
  BE -->|job_id| QS[[split.requests]]
  QS --> SP[split]
  SP -->|fragmentos| R
  SP -->|1 msg por fragmento<br/>exchange tasks, rk=worker_image| QT[[tasks.tp3-worker<br/>quorum, delivery-limit]]
  QT --> W1[worker]
  QT --> W2[worker]
  QT --> W3[worker ...]
  W1 & W2 & W3 -->|resultado| R
  W1 & W2 & W3 -->|fanout results| QJ[[results.joiner]]
  W1 & W2 & W3 -->|fanout results| QM[[results.monitor]]
  QJ --> J[joiner] -->|imagen final + done| R
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
  Internet -->|Ingress público| FE2
```

## Decisiones de diseño
- **Redis como almacén de fragmentos**: por el broker solo viajan mensajes chicos (JSON con referencias) y los bytes van por Redis. Así RabbitMQ no se satura con mensajes de 100 MB.
- **Solapamiento al partir**: cada operación 3×3 necesita 1 px de vecinos, así que una cadena de k operaciones necesita k px. Sin ese solapamiento aparecen líneas en las uniones. Lo verifica `test_split_process_join_equals_full_image`.
- **Sin normalización por el máximo** en Sobel (se recorta a 255). Si cada fragmento normalizara por su propio máximo, los fragmentos no quedarían consistentes entre sí.
- **Idempotencia del joiner**: `SADD` de `fragment_id` y `SET NX` del lock de armado. Los resultados duplicados por reentregas no rompen nada y con varias réplicas del joiner solo una arma la imagen.
- **404 en lugar de 403** cuando un usuario consulta un job ajeno, para no revelar que el job existe.
- TODO (C): diagrama de arquitectura híbrida del Hit #2, con la justificación local o nube de cada servicio, en [hit2/README.md](../hit2/README.md).
