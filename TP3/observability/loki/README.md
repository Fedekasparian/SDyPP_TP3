# Logs centralizados: Fluent Bit + Loki

Complementa al Hit #4: Prometheus junta las **métricas** y Loki los **logs**, y los dos se consultan desde el mismo Grafana. La consigna no lo pide; es una mejora sobre el requisito de logging (registros en memoria y en disco).

```
cada nodo: [Fluent Bit] --lee /var/log/containers--> [Loki] <-- Grafana (Explore -> Loki)
           (DaemonSet)                               (nodepool infra)
```

| Archivo | Qué es |
|---|---|
| [loki-values.yaml](loki-values.yaml) | Loki en modo single binary: un pod en el nodepool `infra`, con un disco de 10 GB `standard` (HDD). Ese tipo de disco no consume la cuota `SSD_TOTAL_GB` de la región. |
| [fluentbit-values.yaml](fluentbit-values.yaml) | Fluent Bit como DaemonSet que tolera todos los taints, así corre también en `infra`. Toma el tail de los logs de los contenedores y el filtro de Kubernetes que trae el chart, y solo cambia el OUTPUT para mandar a Loki con los labels `namespace`, `pod` y `container`. |
| [grafana-datasource.yaml](grafana-datasource.yaml) | ConfigMap con el label `grafana_datasource=1`: el sidecar de Grafana lo carga como fuente de datos sin tocar el release de kube-prometheus-stack. |

## Despliegue
Lo instala el job `observability` de [deploy.yml](../../../.github/workflows/deploy.yml), después de kube-prometheus-stack, con versiones fijas (loki 7.5.0, fluent-bit 0.58.3). A mano, desde la raíz del repo:
```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add fluent https://fluent.github.io/helm-charts
helm upgrade --install loki grafana/loki --version 7.5.0 -n monitoring -f TP3/observability/loki/loki-values.yaml --wait
helm upgrade --install fluent-bit fluent/fluent-bit --version 0.58.3 -n monitoring -f TP3/observability/loki/fluentbit-values.yaml --wait
kubectl apply -f TP3/observability/loki/grafana-datasource.yaml
```

## Verificación
```bash
kubectl -n monitoring get pods -l "app.kubernetes.io/name in (loki,fluent-bit)" -o wide   # loki-0 en infra, un fluent-bit por nodo
kubectl get --raw "/api/v1/namespaces/monitoring/services/loki:3100/proxy/loki/api/v1/label/namespace/values"
```
En Grafana: **Explore → Loki**, y consultas como:
```logql
{namespace="tp3"}
{namespace="tp3", container="backend"}
{namespace="tp3"} |= "error"
```

## Límites
- **Los workers en VMs no aparecen.** Fluent Bit corre solo en los nodos de GKE; habría que instalarlo en cada VM desde el `startup-script` de Terraform.
- **Fluent Bit lee desde que arranca:** los logs anteriores a su instalación no están. Un servicio sin actividad (split, joiner) aparece recién cuando procesa algo.
- **Retención:** la del chart por defecto, en un disco de 10 GB.

## Desinstalar
```bash
helm uninstall fluent-bit loki -n monitoring
kubectl -n monitoring delete configmap loki-datasource
kubectl -n monitoring delete pvc -l app.kubernetes.io/name=loki
```
