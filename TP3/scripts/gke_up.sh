#!/usr/bin/env bash
# Deja el stack de GKE en el estado declarado y sano. Lo usan evidencia-gke.yml,
# r5-gke.yml y estado-gke.yml (necesita gcloud y kubectl ya autenticados).
#   - pool infra con 1 nodo (si alguien lo bajo a 0)
#   - RabbitMQ y Redis listos, ILBs internos con IP (los usan las VMs workers)
#   - apps reiniciadas y listas, Ingress con la IP estatica global tp3-ingress
# Al final escribe INGRESS_IP=<ip> en $GITHUB_ENV (si existe) y en stdout.
set -euo pipefail
Z="${GKE_ZONE:?definir GKE_ZONE}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if ! kubectl get nodes -l pool=infra --no-headers 2>/dev/null | grep -q .; then
  gcloud container clusters resize tp3 --node-pool infra --num-nodes 1 --zone "$Z" --quiet
fi
for _ in $(seq 1 60); do kubectl get nodes -l pool=infra --no-headers 2>/dev/null | grep -q ' Ready' && break; sleep 10; done
kubectl get nodes -L pool

kubectl apply -k "$ROOT/TP3/k8s/infra"
kubectl -n tp3 rollout status statefulset/rabbitmq --timeout=600s
kubectl -n tp3 rollout status statefulset/redis --timeout=300s
for s in rabbitmq-internal redis-internal; do
  for _ in $(seq 1 40); do
    [ -n "$(kubectl -n tp3 get svc $s -o jsonpath='{.status.loadBalancer.ingress[0].ip}')" ] && break; sleep 10
  done
  echo "$s -> $(kubectl -n tp3 get svc $s -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
done

# IP estatica para el Ingress: la URL publica no cambia aunque se recree el Ingress.
gcloud compute addresses describe tp3-ingress --global >/dev/null 2>&1 \
  || gcloud compute addresses create tp3-ingress --global --quiet

# Apps: si algun rollout quedo trabado (pods Pending por un nodo preemptado), el
# restart los reprograma. Se reintenta una vez antes de fallar.
kubectl -n tp3 rollout restart deploy/backend deploy/split deploy/joiner deploy/dlq-monitor deploy/frontend
for d in backend split joiner dlq-monitor frontend; do
  kubectl -n tp3 rollout status deploy/$d --timeout=300s || {
    kubectl -n tp3 get pods -o wide; kubectl -n tp3 get events --sort-by=.lastTimestamp | tail -15
    kubectl -n tp3 rollout restart deploy/$d; kubectl -n tp3 rollout status deploy/$d --timeout=300s
  }
done

# Ingress: se aplica desde el overlay (lleva la anotacion de la IP estatica).
kubectl kustomize "$ROOT/TP3/k8s/overlays/gke" | yq 'select(.kind == "Ingress" or .kind == "BackendConfig")' \
  | kubectl -n tp3 apply -f -
IP=""
for _ in $(seq 1 80); do
  IP=$(kubectl -n tp3 get ingress tp3 -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
  [ -n "$IP" ] && [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://$IP/api/health")" = 200 ] && break
  sleep 15
done
echo "Ingress http://$IP -> $(curl -s --max-time 10 "http://$IP/api/health")"
[ -n "${GITHUB_ENV:-}" ] && echo "INGRESS_IP=$IP" >> "$GITHUB_ENV"
kubectl -n monitoring rollout status statefulset/prometheus-kube-prometheus-stack-prometheus --timeout=600s
kubectl -n monitoring rollout status deploy/kube-prometheus-stack-grafana --timeout=600s
