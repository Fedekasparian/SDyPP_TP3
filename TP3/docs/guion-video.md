# Guion del video (R2, R4 y R5 con Grafana en vivo)

Duración objetivo: **8 a 10 minutos**, una sola toma por bloque. Todo contra **GKE**, con los
workers en VM. Grabar con OBS (pantalla completa y micrófono). Antes de grabar:

```bash
# 1) Estado: el cluster arriba, 2 VMs workers y la URL respondiendo
curl http://<IP>/api/health          # {"backend":"ok","redis":"ok","rabbitmq":"ok"}
# 2) Grafana en local (port-forward al pod)
gcloud container clusters get-credentials tp3 --zone us-central1-a --project tp3distribuidos
kubectl -n monitoring port-forward deploy/kube-prometheus-stack-grafana 3000:3000
kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d
# 3) Tokens: generarlos en una terminal FUERA de cámara (no mostrarlos en el video)
export ADMIN_TOKEN=$(kubectl -n tp3 exec deploy/backend -- python -c "$(cat TP3/scripts/gen_token.py)" admin admin)
export USER_A=$(kubectl -n tp3 exec deploy/backend -- python -c "$(cat TP3/scripts/gen_token.py)" alice user)
export USER_B=$(kubectl -n tp3 exec deploy/backend -- python -c "$(cat TP3/scripts/gen_token.py)" bob user)
export B=http://<IP>/api
```

Dejar abiertos: una terminal, Grafana en el dashboard **TP3** (rango `now-15m`, refresco 5 s) y
la consola de GCP en *Compute Engine → VM instances*.

## 0. Arquitectura (1 min)
- `kubectl get nodes -L pool` → pools `infra` (RabbitMQ, Redis, observabilidad) y `apps`.
- `kubectl -n tp3 get pods -o wide` → las apps en `apps`; **no hay pods de worker**.
- En la consola de GCP: las VMs `tp3-worker-0/1` fuera del cluster. En Grafana, *Status → Targets*
  muestra el job `tp3-vm-workers` en `up`.
- Abrir `http://<IP>/` (el front) y subir una imagen para mostrar el flujo de punta a punta.

## 1. R2: validación antes de encolar (1,5 min)
Mostrar que cada request inválido recibe un 400/413 claro y que **la cola no se mueve**. Para eso,
mirar en Grafana el panel de mensajes publicados mientras se hacen los requests:

```bash
echo hola > /tmp/no.png
curl -s -H "Authorization: Bearer $USER_A" -F files=@/tmp/no.png -F ops=sobel $B/jobs; echo     # 400 formato
curl -s -H "Authorization: Bearer $USER_A" -F files=@TP3/loadtest/sample.png -F ops=rotate $B/jobs; echo  # 400 op inexistente
curl -s -H "Authorization: Bearer $USER_A" -F ops=sobel $B/jobs; echo                              # 400/422 sin archivos
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" $B/stats | jq '.queues'                            # las colas no cambiaron
```

## 2. R4: autenticación, roles y aislamiento con 3 réplicas (2 min)
```bash
kubectl -n tp3 scale deploy/backend --replicas=3 && kubectl -n tp3 get pods -l app=backend
K8S=1 BASE_URL=$B ADMIN_TOKEN=$ADMIN_TOKEN USER_A_TOKEN=$USER_A USER_B_TOKEN=$USER_B \
  bash TP3/scripts/r4_evidence.sh
```
Comentar cada línea: 401 sin token y con token inválido, 403 de user a `/stats`, 202 al submit,
404 cuando **bob** pide el job de **alice** (status, `/events` y resultado), 30 lecturas que caen en
**backends distintos** (el token se valida en cualquier réplica: es stateless) y el job en `done`.

## 3. R5: una corrida de la matriz con Grafana en vivo (3 a 4 min)
Una celda pesada, para que se vea la saturación. En pantalla dividida, la terminal y Grafana:

```bash
cd TP3/loadtest
py gen_images.py 10KB
SMOKE=1 MODE=none BASE_URL=$B RESULTS_DIR=results-video DECLARADAS_CSV= \
  V1_LIST=10KB VA_LIST=10 VC_LIST=50 CELL_HOOK="py prom_celda.py" ./run_matrix.sh
```
(`prom_celda.py` necesita el port-forward de Prometheus en 9090:
`kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090`.)

Narrar en Grafana, en este orden:
1. **Mensajes publicados vs. consumidos** de RabbitMQ: los publicados suben y los consumidos se
   quedan atrás, así que la cola `tasks.tp3-worker` crece.
2. **Latencia p50/p95/p99 por fragmento** y **throughput por servicio**.
3. **CPU por pod y por nodo**: el backend no se satura. La carga está en las VMs.
4. Al terminar, leer la fila en `results-video/summary.md`: p95, `slo_ok` y la columna
   **cuello_de_botella** con el dato que la delata.
5. Mostrar la tabla completa de GKE (`results-gke/summary.md`) y la conclusión del informe (§8.7).

## 4. Cierre (30 s)
Mencionar el Hit 2 híbrido (`TP3/evidencia/hit2/`: la VM de GCP consumiendo de la RabbitMQ local
por Tailscale, con tiempos), y que el cluster queda levantado para la revisión.

Subir el video a YouTube como **no listado** o a Drive con acceso por link, y pegar el link en el
README (sección "Entrega").
