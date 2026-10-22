# Mi parte C — guía personal de trabajo

Este archivo es una guía local para mí. **No agregarlo al commit ni subirlo al
repositorio.** Los cambios de código/documentación de C están en la rama
`feat/c-infra`; esta lista separa lo ya preparado de lo que todavía tengo que
hacer y verificar con mis credenciales y recursos.

## Alcance de C según `PLAN.md`

- Infraestructura GCP con Terraform: bootstrap, GKE y VMs de workers.
- Pipelines de infraestructura, despliegue de aplicaciones y workers.
- Hit #2: diagrama y explicación de la arquitectura híbrida.
- R1: demostrar un `ImagePullBackOff` sin permiso de descarga y luego la descarga
  exitosa con identidad/credenciales correctas.
- Dejar una forma reproducible de levantar el overlay local de Kubernetes.

## Ya preparado en `feat/c-infra`

- [x] Workflow `infra`: pasa `GKE_ZONE` como `TF_VAR_zone`; plan en PR y apply
  fuera de PR.
- [x] Workflow `workers`: plan en PR, apply al merge a `main` o ejecución manual;
  resuelve las IP internas de RabbitMQ y Redis desde GKE.
- [x] Workflow `deploy`: despliega las apps con una matriz, una app por ejecución
  secuencial después de los servicios base.
- [x] `TP3/scripts/local_up.sh`: build de imágenes, carga a Minikube, creación de
  Secrets desde `.env` y aplicación del overlay local.
- [x] `TP3/scripts/r1_evidence.sh`: prueba el fallo y éxito de descarga de una
  imagen privada y guarda la salida bajo `TP3/evidencia/r1/`.
- [x] README de infraestructura actualizado con las variables y el proceso.
- [x] README del Hit #2 con diagrama híbrido, ubicación de servicios y notas de
  consistencia/disponibilidad.

Estos puntos están implementados, pero todavía debo probarlos en mi entorno
real; el código preparado no reemplaza la evidencia de GCP/Minikube.

## Próximos pasos

### 1. Revisar GCP y el estado inicial

- [ ] Confirmar el ID del proyecto GCP, billing habilitado y cuota disponible.
- [ ] Instalar/verificar `gcloud` y Terraform `>= 1.6`.
- [ ] Iniciar sesión:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  gcloud projects list
  ```
- [ ] Verificar si el bucket de estado ya existe antes de aplicar bootstrap.
  No crear dos veces recursos que ya existan ni reemplazar state existente.
- [ ] Revisar la configuración de GCP y acordar con el equipo las regiones/zona,
  las cuotas y cuándo se apagan los recursos para controlar costos.

### 2. Ejecutar el bootstrap una sola vez

Desde Git Bash o WSL:

```bash
cd TP3/infra/terraform/bootstrap
terraform init
terraform plan -var="project_id=<PROJECT_ID>"
terraform apply -var="project_id=<PROJECT_ID>"
```

- [ ] Revisar el plan antes del apply.
- [ ] Guardar los outputs del bootstrap: `wif_provider`,
  `ci_service_account`, `gke_nodes_service_account`,
  `workers_service_account`, `tfstate_bucket` y `registry`.
- [ ] Migrar el state local a GCS siguiendo `provider.tf`: habilitar el backend
  GCS y ejecutar `terraform init -migrate-state` con el bucket correcto.
- [ ] Comprobar que el state remoto está disponible antes de seguir.
- [ ] Cargar valores nuevos en Secret Manager; no ponerlos en Git ni en esta guía:
  ```bash
  openssl rand -base64 24 | gcloud secrets versions add tp3-rabbit-pass --data-file=-
  openssl rand -base64 24 | gcloud secrets versions add tp3-redis-pass --data-file=-
  openssl rand -base64 32 | gcloud secrets versions add tp3-auth-secret --data-file=-
  ```

### 3. Configurar variables de GitHub Actions

En Settings → Secrets and variables → Actions → Variables, cargar:

- [ ] `GCP_PROJECT`: ID del proyecto.
- [ ] `GCP_REGION`: por ejemplo `us-central1`.
- [ ] `GKE_ZONE`: por ejemplo `us-central1-a`.
- [ ] `GCP_WIF_PROVIDER`: output `wif_provider`.
- [ ] `GCP_CI_SA`: output `ci_service_account`.
- [ ] `GKE_NODES_SA`: output `gke_nodes_service_account`.
- [ ] `WORKERS_SA`: output `workers_service_account`.
- [ ] `TF_STATE_BUCKET`: output `tfstate_bucket`.
- [ ] Opcional `WORKER_COUNT`: número deseado de VMs al aplicar cambios de workers.
  Si falta, el workflow usa `0` por seguridad.

No configurar IPs de RabbitMQ/Redis a mano: el workflow `workers` las consulta
desde los LoadBalancers internos de GKE. No guardar contraseñas ni tokens como
variables de texto; los valores de runtime van en Secret Manager.

### 4. Crear GKE y validar los pipelines

- [ ] En Actions, ejecutar `infra` manualmente para crear GKE.
- [ ] Revisar `terraform plan`/logs antes de aceptar cualquier cambio.
- [ ] Confirmar que los node pools `infra` y `apps` estén listos.
- [ ] Ejecutar `deploy` cuando el CI de `main` haya construido las imágenes.
- [ ] Revisar en el workflow que RabbitMQ, Redis, observabilidad y cada app
  terminen sus rollout.
- [ ] Validar con `kubectl get pods -n tp3 -o wide` que la aplicación corre en
  `apps` y RabbitMQ/Redis en `infra`.
- [ ] Verificar los endpoints públicos `/health` y `/api/health`.
- [ ] Coordinar con D cualquier dependencia de monitoreo/alertas y con B las
  necesidades de servicios o cambios de manifiestos.

### 5. Probar los workers fuera del cluster (Hit #2 / Hit #3)

- [ ] Confirmar que RabbitMQ y Redis tienen IP interna asignada:
  `kubectl -n tp3 get svc rabbitmq-internal redis-internal`.
- [ ] Probar `workers` con `worker_count=1` desde `workflow_dispatch`; verificar
  que la VM aparezca y que el startup script logre leer Secret Manager, descargar
  la imagen y conectarse a RabbitMQ/Redis.
- [ ] Comprobar desde los logs/health que la VM está procesando tareas.
- [ ] Probar el teardown con `worker_count=0` y comprobar que no queden VMs.
- [ ] Solo dejar workers activos si hay una corrida acordada; revisar costos y
  cuotas al terminar.

### 6. Levantar Kubernetes local y verificar R1

- [ ] Instalar Docker Desktop, Minikube, `kubectl`, Docker Compose y Git Bash/WSL.
- [ ] Copiar `.env.example` a `.env` y cambiar `RABBIT_PASS` y `AUTH_SECRET` por
  valores locales nuevos. Asegurar que `RABBIT_URL` use el mismo password:
  `amqp://tp3:<password>@rabbitmq:5672/`.
- [ ] No agregar `.env` al repositorio; ya está excluido por `.gitignore`.
- [ ] Desde la raíz del repo, ejecutar `bash TP3/scripts/local_up.sh`.
- [ ] Esperar los rollouts y comprobar `kubectl get pods -n tp3`.
- [ ] Abrir el frontend con:
  ```bash
  kubectl -n tp3 port-forward svc/frontend 8081:80
  ```
  y probar `http://localhost:8081`.
- [ ] Para R1, elegir una imagen/tag existente y privado del Artifact Registry,
  tener `gcloud` autenticado con permiso de lectura y ejecutar:
  ```bash
  R1_IMAGE=us-central1-docker.pkg.dev/<PROJECT_ID>/tp3/backend:<TAG> \
    bash TP3/scripts/r1_evidence.sh
  ```
- [ ] Comprobar que la salida muestra primero `ImagePullBackOff` y luego el
  rollout exitoso usando `imagePullSecret`.
- [ ] Revisar el archivo generado en `TP3/evidencia/r1/`; guardar evidencia
  solicitada (captura/log) sin incluir tokens.
- [ ] Al terminar, borrar el namespace de prueba para eliminar el Secret temporal:
  `kubectl delete namespace r1-evidence`.

### 7. Cierre y entrega

- [ ] Completar cualquier cambio que salga al ejecutar pruebas reales; no afirmar
  que GCP o R1 están validados sin evidencia.
- [ ] Revisar Terraform con `terraform fmt -check`, `terraform validate` y plan
  contra el backend correcto.
- [ ] Revisar CI (gitleaks/tests/build) y los workflows de infraestructura.
- [ ] Hacer commits chicos y un PR de `feat/c-infra` a `main`.
- [ ] Confirmar que este archivo personal no aparece en el commit ni en el PR:
  `MI_PARTE_C_LOCAL.md`.
- [ ] Dejar el costo controlado: `worker_count=0` cuando no se usan workers y
  destruir GKE solo cuando el equipo confirme que ya no lo necesita.

## Referencias del repositorio

- `PLAN.md`: reparto, alcance, dependencias y checklist final.
- `TP3/infra/README.md`: bootstrap, variables de GitHub, costos.
- `TP3/infra/terraform/bootstrap/`: bucket, registry, IAM, WIF y secretos.
- `TP3/infra/terraform/gke/`: cluster y pools.
- `TP3/infra/terraform/workers/`: VMs, startup script y firewall de métricas.
- `TP3/hit2/README.md`: arquitectura híbrida y comandos de workers.
- `.github/workflows/infra.yml`, `workers.yml`, `deploy.yml`: pipelines de C.
