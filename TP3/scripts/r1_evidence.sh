#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${R1_IMAGE:?Set R1_IMAGE to an existing private Artifact Registry image.}"
NAMESPACE="${R1_NAMESPACE:-r1-evidence}"
REGISTRY_HOST="${IMAGE%%/*}"

for command in gcloud kubectl tee; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 1
  fi
done

CONTEXT="$(kubectl config current-context)"
# Debe correr en el cluster LOCAL (k3d/k3s/minikube), que no tiene acceso al registry.
if [[ "$CONTEXT" == gke_* ]]; then
  echo "Contexto GKE detectado ($CONTEXT): usar un cluster local sin credenciales del registry." >&2
  exit 1
fi

OUTPUT_DIR="$ROOT/TP3/evidencia/r1"
mkdir -p "$OUTPUT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/r1-$(date +%Y%m%d-%H%M%S).txt"
exec > >(tee "$OUTPUT_FILE") 2>&1

echo "Context: $CONTEXT"
echo "Image: $IMAGE"
echo "Evidence: $OUTPUT_FILE"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" delete deployment r1-probe --ignore-not-found=true
kubectl -n "$NAMESPACE" delete secret artifact-registry --ignore-not-found=true

cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: r1-probe
  namespace: $NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: r1-probe
  template:
    metadata:
      labels:
        app: r1-probe
    spec:
      containers:
        - name: probe
          image: $IMAGE
          imagePullPolicy: Always
          command: ["sh", "-c", "sleep 3600"]
EOF

reason=""
for _ in $(seq 1 36); do
  reason="$(kubectl -n "$NAMESPACE" get pods -l app=r1-probe \
    -o jsonpath='{.items[0].status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)"
  if [[ "$reason" == "ImagePullBackOff" ]]; then
    break
  fi
  sleep 5
done

if [[ "$reason" != "ImagePullBackOff" ]]; then
  echo "Expected ImagePullBackOff without registry credentials; observed: ${reason:-no waiting reason}." >&2
  kubectl -n "$NAMESPACE" describe pods -l app=r1-probe
  exit 1
fi

echo "Expected failure without imagePullSecret:"
kubectl -n "$NAMESPACE" get pods -l app=r1-probe -o wide
kubectl -n "$NAMESPACE" describe pods -l app=r1-probe

TOKEN="$(gcloud auth print-access-token)"
kubectl -n "$NAMESPACE" create secret docker-registry artifact-registry \
  --docker-server="$REGISTRY_HOST" \
  --docker-username=oauth2accesstoken \
  --docker-password="$TOKEN" \
  --docker-email="${GITHUB_ACTOR:-r1-evidence@example.invalid}" \
  --dry-run=client -o yaml | kubectl apply -f -
unset TOKEN

kubectl -n "$NAMESPACE" patch deployment r1-probe --type=merge \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"artifact-registry"}]}}}}'
kubectl -n "$NAMESPACE" rollout status deployment/r1-probe --timeout=300s
echo "Successful pull with imagePullSecret:"
kubectl -n "$NAMESPACE" get pods -l app=r1-probe -o wide
kubectl -n "$NAMESPACE" describe pods -l app=r1-probe
kubectl -n "$NAMESPACE" get events --sort-by=.lastTimestamp
echo "Evidence saved to $OUTPUT_FILE"
