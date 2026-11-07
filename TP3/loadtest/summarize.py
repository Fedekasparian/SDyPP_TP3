"""Junta los JSON de results/ en results/summary.csv y results/summary.md.

A diferencia de un resumen que lista "lo que haya", este emite SIEMPRE el
producto cruzado completo de la matriz (108 celdas para R5). Cada celda sale de
una de tres formas:

  - medida           -> los numeros del JSON de k6
  - declarada        -> el motivo de celdas_declaradas.csv, en vez de numeros
  - SIN MEDIR        -> nadie la corrio ni la declaro. Es un error a corregir,
                        y aparece en la tabla justamente para que se vea.

El motivo es que R5 es un entregable que no puede tener huecos: si una celda se
corta por timeout y solo listaramos los JSON existentes, la tabla saldria con
102 filas y nada avisaria.

La columna `cuello_de_botella` sale de lo que Prometheus vio durante la celda
(results-*/<celda>.prom.json, que escribe prom_celda.py) aplicando la regla de
`cuello_de_botella()`. Si la celda no tiene captura (la corrida local del 23/10
no la guardaba), la columna lo dice en vez de quedar vacia.

SLO (ver TP3/loadtest/README.md, "Objetivo de negocio"):
  - interactivo (VA=1):  p95 end-to-end <= SLO_P95_S          (10 s)
  - lote (VA>1):         p95 end-to-end <= SLO_P95_LOTE_S     (45 s)
  - en ambos:            tasa de error  <  SLO_ERR            (1 %)
SLO_MODO=legacy reproduce el SLO unico de la corrida local (p95 < 10 s, error < 5 %).
"""
import csv
import json
import os
import re
from pathlib import Path

SLO_MODO = os.getenv("SLO_MODO", "negocio")
SLO_P95_S = float(os.getenv("SLO_P95_S", "10"))
SLO_P95_LOTE_S = float(os.getenv("SLO_P95_LOTE_S", "45" if SLO_MODO == "negocio" else "10"))
SLO_ERR = float(os.getenv("SLO_ERR", "0.01" if SLO_MODO == "negocio" else "0.05"))
MATRIX = os.getenv("MATRIX", "r5")

# Umbrales de la regla de cuello de botella.
COLA_MIN = int(os.getenv("COLA_MIN", "50"))          # mensajes listos para considerar que una cola se acumula
CPU_VM_SAT = float(os.getenv("CPU_VM_SAT", "0.7"))   # nucleos: el worker es un proceso Python (~1 nucleo util)
CPU_POD_SAT = float(os.getenv("CPU_POD_SAT", "0.8")) # fraccion del limit de CPU del pod
CPU_NODO_SAT = float(os.getenv("CPU_NODO_SAT", "0.85"))

# El producto cruzado que exige cada matriz. Tiene que coincidir con las listas
# de run_matrix.sh. VB es la CANTIDAD de operaciones encadenadas, no la cadena.
ESPERADAS = {
    "r5": {
        "V3": ["2", "6"],
        "V1": ["10KB", "1MB"],
        "VA": ["1", "10", "50"],
        "VB": ["1", "2", "3"],
        "VC": ["1", "10", "50"],
    },
    "hit3": {
        "V3": ["1", "2", "4", "8"],
        "V1": ["1KB", "10KB", "100KB", "1MB", "10MB", "100MB"],
        "VA": ["1"],
        "VB": ["1"],
        "VC": ["1", "5", "10", "25", "50"],
    },
}

base_dir = Path(__file__).parent
res_dir = base_dir / os.getenv("RESULTS_DIR", "results")
pattern = re.compile(
    r"(?P<matrix>\w+?)_V1-(?P<V1>\w+)_V3-(?P<V3>\d+)_VA-(?P<VA>\d+)_VB-(?P<VB>\d+)_VC-(?P<VC>\d+)"
)
CLAVE = ("V1", "V3", "VA", "VB", "VC")


def leer_declaradas():
    """celdas_declaradas.csv -> {(V1,V3,VA,VB,VC): motivo} de ESTA matriz.

    La columna `matriz` es opcional y vale "r5" cuando falta, para que sigan
    siendo validas las filas escritas antes de que existiera la tabla del Hit #3.
    El filtro hace falta porque las dos matrices COMPARTEN CLAVES: por ejemplo
    (V1=10KB, V3=2, VA=1, VB=1, VC=1) es una celda de R5 y tambien una del
    Hit #3. Sin filtrar, declarar una de las dos declararia la otra sin querer.
    """
    # DECLARADAS_CSV="" desactiva las declaraciones: en GKE una celda no medida
    # tiene que verse como SIN MEDIR y no heredar un motivo de la corrida local.
    nombre = os.getenv("DECLARADAS_CSV", "celdas_declaradas.csv")
    f = base_dir / nombre
    if not nombre or not f.is_file():
        return {}
    # Las lineas que empiezan con # son comentarios: csv no los filtra solo.
    lineas = [ln for ln in f.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return {
        tuple(fila[c] for c in CLAVE): fila["motivo"]
        for fila in csv.DictReader(lineas)
        if (fila.get("matriz") or "r5") == MATRIX
    }


def leer_medidas():
    """results/*.json de esta matriz -> {(V1,V3,VA,VB,VC): metricas}."""
    medidas = {}
    for f in sorted(res_dir.glob("*.json")):
        if f.name.endswith(".prom.json"):
            continue
        m = pattern.match(f.stem)
        if not m or m.group("matrix") != MATRIX:
            continue
        medidas[tuple(m.group(c) for c in CLAVE)] = json.loads(f.read_text())["metrics"]
    return medidas


def meseta_de(clave):
    """Lee results/<celda>.meta y devuelve la meseta con la que se midio.

    Las celdas mas pesadas no entran en la memoria de la maquina con la meseta
    normal, asi que se midieron con una mas corta. Mezclarlas en la tabla sin
    decirlo seria reportar algo falso: por eso la columna existe.
    """
    v1, v3, va, vb, vc = clave
    f = res_dir / f"{MATRIX}_V1-{v1}_V3-{v3}_VA-{va}_VB-{vb}_VC-{vc}.meta"
    if not f.exists():
        return "?"
    for linea in f.read_text(encoding="utf-8").splitlines():
        if linea.startswith("DURATION="):
            return linea.split("=", 1)[1].strip()
    return "?"


def cola(colas, prefijo):
    return max((v for k, v in colas.items() if k.startswith(prefijo)), default=0)


def cuello_de_botella(clave, metrics):
    """Regla explicita sobre lo que vio Prometheus en la ventana de la celda.

    Se recorre el pipeline en orden (entrada -> split -> workers -> joiner) y se
    reporta la PRIMERA etapa saturada, con el dato que la delata, porque una
    etapa saturada aguas arriba esconde a las de abajo (no les llega trabajo).
    """
    f = res_dir / (f"{MATRIX}_V1-{clave[0]}_V3-{clave[1]}_VA-{clave[2]}_VB-{clave[3]}_VC-{clave[4]}.prom.json")
    if not f.exists():
        return "sin captura de Prometheus (corrida local del 23/10; ver matriz GKE)"
    p = json.loads(f.read_text(encoding="utf-8"))
    colas = p.get("colas", {})
    pods = p.get("cpu_pod_frac", {})
    vms = p.get("cpu_vm", {})
    nodos = p.get("cpu_nodo", {})
    c_split, c_tasks, c_res = cola(colas, "split"), cola(colas, "tasks.tp3"), cola(colas, "results.joiner")
    cpu_vm = max(vms.values(), default=0)
    timeouts = metrics.get("job_timeouts", {}).get("count", 0)

    if pods.get("backend", 0) >= CPU_POD_SAT:
        return f"backend: CPU al {pods['backend']:.0%} del limit (ingreso HTTP)"
    if c_split >= COLA_MIN and c_split >= c_tasks / 4:
        return f"split: cola split.requests max {c_split:.0f}, CPU split {pods.get('split', 0):.0%} del limit"
    if c_tasks >= COLA_MIN:
        if cpu_vm >= CPU_VM_SAT:
            return f"workers (VMs): CPU {cpu_vm:.2f} nucleos/VM, cola tasks max {c_tasks:.0f}"
        return (f"workers (VMs) por I/O: cola tasks max {c_tasks:.0f} con CPU {cpu_vm:.2f} nucleos/VM "
                f"(fragmentos ida y vuelta a Redis por la red VM-cluster)")
    if c_res >= COLA_MIN:
        return f"joiner: cola results.joiner max {c_res:.0f}, CPU joiner {pods.get('joiner', 0):.0%}"
    nodo, cpu_n = max(nodos.items(), key=lambda kv: kv[1], default=("", 0))
    if cpu_n >= CPU_NODO_SAT:
        return f"nodo GKE {nodo} al {cpu_n:.0%} de CPU"
    if timeouts:
        return f"sin cola acumulada pero {timeouts} timeouts: revisar ingreso (Ingress/red)"
    return f"ninguno: sin saturacion (colas max {max(c_split, c_tasks, c_res):.0f}, CPU VM {cpu_vm:.2f}); domina el recorrido y el polling"


def slo_ok(clave, p95, err):
    limite = SLO_P95_S if clave[2] == "1" else SLO_P95_LOTE_S
    return "si" if p95 < limite and err < SLO_ERR else "no"


def fila_medida(clave, metrics):
    lat = dict(metrics.get("job_latency", {}))
    err = metrics.get("job_errors", {}).get("value", 0.0)
    # Sin jobs terminados k6 reporta los percentiles en 0: tomados tal cual, la celda saldria
    # con p95 = 0 y slo_ok = si. Ningun job dentro de la ventana es justamente lo contrario.
    if not lat.get("count"):
        lat = {"count": 0}
    p95 = lat.get("p(95)", float("nan")) / 1000
    return {
        **dict(zip(CLAVE, clave)),
        "estado": "medida",
        "meseta": meseta_de(clave),
        "p50_s": round(lat.get("med", float("nan")) / 1000, 3),
        "p95_s": round(p95, 3),
        "p99_s": round(lat.get("p(99)", float("nan")) / 1000, 3),
        "jobs_ok": lat.get("count", 0),
        "throughput_req_s": round(metrics.get("http_reqs", {}).get("rate", 0.0), 2),
        "tasa_error": round(err, 4),
        "dlq": metrics.get("job_dlq", {}).get("count", 0),
        "timeouts": metrics.get("job_timeouts", {}).get("count", 0),
        "invalidos_rechazados": metrics.get("invalid_rejected", {}).get("count", 0),
        "slo_ok": slo_ok(clave, p95, err),
        "cuello_de_botella": cuello_de_botella(clave, metrics),
    }


def fila_sin_medir(clave, motivo):
    fila = {**dict(zip(CLAVE, clave)), "estado": motivo, "meseta": "-"}
    for col in ("p50_s", "p95_s", "p99_s", "jobs_ok", "throughput_req_s", "tasa_error",
                "dlq", "timeouts", "invalidos_rechazados", "slo_ok", "cuello_de_botella"):
        fila[col] = "-"
    return fila


esperadas = ESPERADAS[MATRIX]
declaradas = leer_declaradas()
medidas = leer_medidas()

rows, n_medidas, n_declaradas, faltantes = [], 0, 0, []
for v3 in esperadas["V3"]:
    for v1 in esperadas["V1"]:
        for va in esperadas["VA"]:
            for vb in esperadas["VB"]:
                for vc in esperadas["VC"]:
                    clave = (v1, v3, va, vb, vc)
                    if clave in medidas:
                        rows.append(fila_medida(clave, medidas[clave]))
                        n_medidas += 1
                    elif clave in declaradas:
                        rows.append(fila_sin_medir(clave, declaradas[clave]))
                        n_declaradas += 1
                    else:
                        rows.append(fila_sin_medir(clave, "SIN MEDIR"))
                        faltantes.append(clave)

res_dir.mkdir(exist_ok=True)
cols = list(rows[0])
# Una salida por matriz. R5 conserva el nombre sin sufijo porque el informe ya
# cita results/summary.md; si las dos escribieran ahi, correr el Hit #3 borraria
# la tabla de R5 y la cita del informe apuntaria a otra tabla.
sufijo = "" if MATRIX == "r5" else f"_{MATRIX}"
with open(res_dir / f"summary{sufijo}.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
(res_dir / f"summary{sufijo}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

total = len(rows)
print(f"matriz {MATRIX}: {total} celdas esperadas | {n_medidas} medidas | "
      f"{n_declaradas} declaradas | {len(faltantes)} SIN MEDIR")
mesetas = {}
for r in rows:
    if r["estado"] == "medida":
        mesetas[r["meseta"]] = mesetas.get(r["meseta"], 0) + 1
if len(mesetas) > 1:
    print("  ATENCION: la matriz tiene mesetas mezcladas, hay que declararlo en el informe:")
    for m, n in sorted(mesetas.items()):
        print(f"    meseta {m}: {n} celdas")

if faltantes:
    print("  faltan (correrlas o declararlas en celdas_declaradas.csv):")
    for clave in faltantes:
        print("   ", dict(zip(CLAVE, clave)))
