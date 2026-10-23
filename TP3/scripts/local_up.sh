#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Cluster local: la catedra (Practica 0) usa k3s (Linux/WSL2) o k3d (Windows/macOS).
# CLUSTER=k3d (default si esta instalado) | k3s | minikube
CLUSTER="${CLUSTER:-$(command -v k3d >/dev/null 2>&1 && echo k3d || (command -v k3s >/dev/null 2>&1 && echo k3s || echo minikube))}"
K3D_NAME="${K3D_NAME:-tp3}"
case "$CLUSTER" in
  k3d) REQUIRED=(docker k3d kubectl) ;;
  k3s) REQUIRED=(docker k3s kubectl) ;;
  minikube) REQUIRED=(docker minikube kubectl) ;;
  *) echo "CLUSTER debe ser k3d, k3s o minikube (actual: $CLUSTER)" >&2; exit 1 ;;
esac
for command in "${REQUIRED[@]}"; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 1
  fi
done
echo "Cluster local: $CLUSTER"

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example to .env and set RABBIT_PASS and AUTH_SECRET first." >&2
  exit 1
fi

set -a
# .env es configuracion shell-compatible; se quitan los \r por si se edito en Windows.
source <(sed 's/\r$//' .env)
set +a

if [[ -z "${RABBIT_USER:-}" || -z "${RABBIT_PASS:-}" || -z "${RABBIT_URL:-}" || -z "${AUTH_SECRET:-}" ]]; then
  echo "RABBIT_USER, RABBIT_PASS, RABBIT_URL and AUTH_SECRET must be set in .env." >&2
  exit 1
fi

# El Deployment local de RabbitMQ (infra-local.yaml) tiene el usuario fijo "tp3".
if [[ "$RABBIT_USER" != "tp3" ]]; then
  echo "RABBIT_USER debe ser 'tp3' para el overlay local (o cambia infra-local.yaml)." >&2
  exit 1
fi
if [[ "$RABBIT_URL" != *"${RABBIT_USER}:${RABBIT_PASS}@"* ]]; then
  echo "RABBIT_URL debe usar RABBIT_USER y RABBIT_PASS del .env (amqp://tp3:<pass>@rabbitmq:5672/)." >&2
  exit 1
fi

SERVICES=(backend split joiner worker dlq-monitor frontend)

case "$CLUSTER" in
  k3d)
    k3d cluster list "$K3D_NAME" >/dev/null 2>&1 || k3d cluster create "$K3D_NAME"
    kubectl config use-context "k3d-$K3D_NAME"
    ;;
  minikube) minikube start --driver=docker ;;
  k3s) ;; # k3s ya corre como servicio; kubectl debe apuntar a ~/.kube/config
esac

docker compose build "${SERVICES[@]}"
for service in "${SERVICES[@]}"; do
  case "$CLUSTER" in
    k3d) k3d image import "tp3/$service:dev" -c "$K3D_NAME" ;;
    minikube) minikube image load "tp3/$service:dev" ;;
    k3s) docker save "tp3/$service:dev" | sudo k3s ctr images import - ;;
  esac
done

kubectl create namespace tp3 --dry-run=client -o yaml | kubectl apply -f -
kubectl -n tp3 create secret generic rabbitmq-auth \
  --from-literal="rabbitmq-password=$RABBIT_PASS" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n tp3 create secret generic tp3-secrets \
  --from-literal="RABBIT_URL=$RABBIT_URL" \
  --from-literal="REDIS_URL=${REDIS_URL:-redis://redis:6379/0}" \
  --from-literal="AUTH_SECRET=$AUTH_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k TP3/k8s/overlays/local
for deployment in rabbitmq redis backend split joiner worker dlq-monitor frontend; do
  kubectl -n tp3 rollout status "deployment/$deployment" --timeout=300s
done

echo "Local stack is ready. Run: kubectl -n tp3 port-forward svc/frontend 8081:80"
