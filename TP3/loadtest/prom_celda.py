"""Captura lo que vio Prometheus durante UNA celda de la matriz.

Lo llama run_matrix.sh (CELL_HOOK) al terminar cada celda:

    python prom_celda.py <celda> <epoch_inicio> <epoch_fin> <dir_resultados>

Escribe <dir_resultados>/<celda>.prom.json con, para la ventana de la celda:
  - colas:        maximo de mensajes listos por cola (split, tasks, results)
  - cpu_vm:       CPU promedio de cada VM worker (nucleos, process_cpu del worker)
  - cpu_pod_frac: CPU promedio de cada app del cluster como fraccion de su limit
  - cpu_nodo:     CPU maxima de cada nodo GKE (fraccion)
  - http_p95_s:   p95 de la latencia HTTP del backend
  - worker_p95_s: p95 del procesamiento de un fragmento en el worker
  - procesados:   tareas procesadas por servicio en la ventana

summarize.py lee ese archivo y decide la columna cuello_de_botella. Separar la
captura (aca) de la regla (alla) permite cambiar los umbrales y regenerar la
tabla sin volver a correr la carga.

Solo usa la biblioteca estandar: corre en el runner sin instalar nada.
PROM_URL apunta al Prometheus (por defecto, un port-forward en localhost:9090).
"""
import json
import os
import sys
import urllib.parse
import urllib.request

PROM = os.getenv("PROM_URL", "http://localhost:9090")


def q(expr, t):
    url = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": t})
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    if data.get("status") != "success":
        return []
    return data["data"]["result"]


def por(expr, t, label):
    out = {}
    for s in q(expr, t):
        try:
            out[s["metric"].get(label, "?")] = round(float(s["value"][1]), 4)
        except (ValueError, KeyError):
            pass
    return out


def escalar(expr, t):
    r = q(expr, t)
    try:
        v = float(r[0]["value"][1])
        return None if v != v else round(v, 4)  # NaN -> None
    except (IndexError, KeyError, ValueError):
        return None


def app_de(pod):
    # backend-7c9f8d-abcde -> backend ; dlq-monitor-xxx-yyy -> dlq-monitor
    partes = pod.split("-")
    return "-".join(partes[:-2]) if len(partes) > 2 else pod


def main():
    celda, t0, t1, out_dir = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    d = max(t1 - t0, 30)
    w = f"{d}s"
    res = {"celda": celda, "t0": t0, "t1": t1, "ventana_s": d}

    colas = por(f'max by (queue) (max_over_time(rabbitmq_queue_messages_ready{{queue!=""}}[{w}]))', t1, "queue")
    if not colas:  # fallback: el gauge que publica dlq-monitor
        colas = por(f"max by (queue) (max_over_time(tasks_queued[{w}]))", t1, "queue")
    res["colas"] = colas

    res["cpu_vm"] = por(
        f'avg_over_time(sum by (instance) (rate(process_cpu_seconds_total{{job="tp3-vm-workers"}}[1m]))[{w}:15s])',
        t1, "instance")

    uso = por(
        f'avg_over_time(sum by (pod) (rate(container_cpu_usage_seconds_total{{namespace="tp3",container!=""}}[1m]))[{w}:15s])',
        t1, "pod")
    lim = por('sum by (pod) (kube_pod_container_resource_limits{namespace="tp3",resource="cpu"})', t1, "pod")
    frac = {}
    for pod, u in uso.items():
        if lim.get(pod):
            a = app_de(pod)
            frac[a] = max(frac.get(a, 0.0), round(u / lim[pod], 3))
    res["cpu_pod_frac"] = frac

    res["cpu_nodo"] = por(
        f'max_over_time((1 - avg by (instance) (rate(node_cpu_seconds_total{{mode="idle"}}[1m])))[{w}:15s])',
        t1, "instance")
    res["http_p95_s"] = escalar(
        f"histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[{w}])))", t1)
    res["worker_p95_s"] = escalar(
        f'histogram_quantile(0.95, sum by (le) (rate(task_duration_seconds_bucket{{service="worker"}}[{w}])))', t1)
    res["procesados"] = por(f"sum by (service) (increase(tasks_processed_total[{w}]))", t1, "service")

    path = os.path.join(out_dir, f"{celda}.prom.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(f"   prometheus: colas={colas} cpu_vm={res['cpu_vm']} cpu_pod={frac}")


if __name__ == "__main__":
    main()
