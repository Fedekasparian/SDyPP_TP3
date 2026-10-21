#!/usr/bin/env bash
# Evidencia reproducible de R4 (roles, aislamiento, stateless con 3 replicas).
#   BASE_URL=http://<ip-publica>/api ADMIN_TOKEN=... USER_A_TOKEN=... USER_B_TOKEN=... ./r4_evidence.sh
# Con K8S=1 ademas escala el backend a 3 replicas y consulta repetidamente.
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"
IMG="${IMG:-$(dirname "$0")/../loadtest/sample.png}"
pass=0; fail=0

check() {  # check <descripcion> <codigo-esperado(s) separados por |> <codigo-obtenido>
  if [[ "|$2|" == *"|$3|"* ]]; then echo "OK   $1 -> $3"; pass=$((pass+1));
  else echo "FAIL $1 -> $3 (esperado $2)"; fail=$((fail+1)); fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

if [[ "${K8S:-0}" == "1" ]]; then
  kubectl -n tp3 scale deploy/backend --replicas=3
  kubectl -n tp3 rollout status deploy/backend --timeout=120s
  kubectl -n tp3 get pods -l app=backend -o wide
fi

check "sin token -> 401" 401 "$(code "$BASE_URL/jobs")"
check "usuario en /stats -> 403" 403 "$(code -H "Authorization: Bearer $USER_A_TOKEN" "$BASE_URL/stats")"

JOB_A=$(curl -s -H "Authorization: Bearer $USER_A_TOKEN" -F "files=@$IMG" -F ops=sobel "$BASE_URL/jobs" \
  | sed -n 's/.*"job_id":"\([^"]*\)".*/\1/p')
echo "job de A: $JOB_A"
check "usuario B consulta job de A -> 403/404" "403|404" \
  "$(code -H "Authorization: Bearer $USER_B_TOKEN" "$BASE_URL/jobs/$JOB_A")"
check "admin en /stats -> 200" 200 "$(code -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/stats")"

# Stateless: 20 consultas seguidas del mismo job caen en replicas distintas y todas responden 200.
ok=0
for _ in $(seq 1 20); do
  [[ "$(code -H "Authorization: Bearer $USER_A_TOKEN" "$BASE_URL/jobs/$JOB_A")" == 200 ]] && ok=$((ok+1))
done
check "20 consultas del job de A entre replicas" 20 "$ok"

echo "---- $pass OK, $fail FAIL"
[[ $fail -eq 0 ]]
