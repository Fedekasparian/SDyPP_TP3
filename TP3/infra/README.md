# Infraestructura (Terraform, GCP)

**Responsable: Integrante C**

```
terraform/
  bootstrap/  una sola vez a mano: bucket de state, Artifact Registry, SAs, OIDC para GitHub, Secret Manager
  gke/        cluster con nodepools infra y apps (pipeline infra.yml)
  workers/    VMs workers fuera del cluster (pipeline workers.yml)
```
Cada módulo tiene `provider.tf`, `variables.tf`, `main.tf` y `outputs.tf`. El state es remoto en GCS, con lock nativo. **Nunca** se commitea un `terraform.tfstate`; `.gitignore` ya lo excluye.

## Setup inicial (en orden)
1. Crear el proyecto GCP, activar billing o créditos e instalar `gcloud` y `terraform`.
2. Correr el bootstrap:
   ```bash
   gcloud auth application-default login
   cd TP3/infra/terraform/bootstrap
   terraform init && terraform apply -var project_id=<PROJECT>
   # migrar su state al bucket recién creado (ver el comentario en provider.tf)
   ```
3. Cargar los valores de los secretos en Secret Manager. Esto es local y no va al repo:
   ```bash
   openssl rand -base64 24 | gcloud secrets versions add tp3-rabbit-pass --data-file=-
   openssl rand -base64 24 | gcloud secrets versions add tp3-redis-pass  --data-file=-
   openssl rand -base64 32 | gcloud secrets versions add tp3-auth-secret --data-file=-
   ```
4. Cargar las **GitHub Variables** (Settings → Secrets and variables → Actions → *Variables*). No son secretos, porque la autenticación es por OIDC y no hay claves:

   | Variable | Valor |
   |---|---|
   | `GCP_PROJECT` | id del proyecto |
   | `GCP_REGION` | `us-central1` |
   | `GKE_ZONE` | `us-central1-a` |
   | `GCP_WIF_PROVIDER` | output `wif_provider` |
   | `GCP_CI_SA` | output `ci_service_account` |
   | `GKE_NODES_SA` | output `gke_nodes_service_account` |
   | `WORKERS_SA` | output `workers_service_account` |
   | `TF_STATE_BUCKET` | output `tfstate_bucket` |
   | `RABBIT_INTERNAL_IP` / `REDIS_INTERNAL_IP` | después del primer deploy: `kubectl -n tp3 get svc rabbitmq-internal redis-internal` |

5. Ejecutar el workflow `infra` (dispatch), después `ci` (push a main) y `deploy`, que corre solo después de `ci`. Para los workers, `workers` con dispatch y `worker_count=N`.
6. Health-checks públicos: `http://<ingress-ip>/health` y `http://<ingress-ip>/api/health`.

## Costos
- Los nodos y las VMs son **spot** por defecto.
- Al terminar cada sesión: `workers` con `worker_count=0`, y si no se usa el cluster por un rato, `terraform destroy` en `gke/`.
