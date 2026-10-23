# R1: evidencia de registry privado

**Responsable: C**

El registry `REGION-docker.pkg.dev/PROJECT/tp3` es privado. Solo pueden leerlo los SA `tp3-gke-nodes` y `tp3-workers` ([bootstrap/main.tf](../infra/terraform/bootstrap/main.tf)).

## 1. Pull rechazado (sin identidad válida)
Opciones (elegir una y capturar):
- **Desde afuera:** `docker pull REGION-docker.pkg.dev/PROJECT/tp3/backend:latest` sin estar logueado debe devolver `denied` o `unauthenticated`.
- **En Kubernetes:** en el cluster local (k3s o minikube), sin pull secret:
  ```bash
  kubectl -n tp3 run r1-sin-acceso --image=REGION-docker.pkg.dev/PROJECT/tp3/backend:latest
  kubectl -n tp3 get pod r1-sin-acceso   # -> ErrImagePull / ImagePullBackOff
  kubectl -n tp3 describe pod r1-sin-acceso | grep -A3 Events
  ```

## 2. El mismo despliegue funcionando con la identidad correcta
- **En GKE:** los nodos usan `tp3-gke-nodes` (rol `artifactregistry.reader`) y `kubectl -n tp3 get pods` muestra todo en `Running`.
- **En el cluster local:** con un pull secret de token de vida corta (1 h, sin claves estáticas):
  ```bash
  kubectl -n tp3 create secret docker-registry ar-pull \
    --docker-server=REGION-docker.pkg.dev --docker-username=oauth2accesstoken \
    --docker-password="$(gcloud auth print-access-token)"
  kubectl -n tp3 run r1-con-acceso --image=REGION-docker.pkg.dev/PROJECT/tp3/backend:latest \
    --overrides='{"spec":{"imagePullSecrets":[{"name":"ar-pull"}]}}'
  ```
- **VMs workers:** `journalctl -u google-startup-scripts` muestra `docker pull` OK con el SA de la VM.

## Evidencia registrada
Se corrió `r1_evidence.sh` en un cluster local k3d (`k3d-sdypp`) contra
`us-central1-docker.pkg.dev/tp3distribuidos/tp3/backend:latest`. La salida completa está en
[r1-20261022-235207.txt](../evidencia/r1/r1-20261022-235207.txt):

1. **Sin `imagePullSecret`:** el pod `r1-probe` queda en `ImagePullBackOff` (el registry rechaza el pull anónimo).
2. **Con el secret de token de vida corta:** el mismo Deployment hace `rollout` y el pod pasa a `Running`.
   El evento `Successfully pulled image ... (83793537 bytes)` confirma que la imagen vino del registry privado.

En GKE, el deploy de cada push a `main` es la misma prueba del lado positivo: los nodos bajan las
imágenes con el SA `tp3-gke-nodes` y los pods quedan `Running` (`kubectl -n tp3 get pods`).
