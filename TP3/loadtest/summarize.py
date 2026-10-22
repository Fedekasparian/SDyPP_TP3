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

La columna `cuello_de_botella` se completa a mano mirando Grafana durante la
corrida.
"""
import csv
import json
import os
import re
from pathlib import Path

SLO_P95_S = float(os.getenv("SLO_P95_S", "10"))
SLO_ERR = float(os.getenv("SLO_ERR", "0.05"))
MATRIX = os.getenv("MATRIX", "r5")

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
res_dir = base_dir / "results"
pattern = re.compile(
    r"(?P<matrix>\w+?)_V1-(?P<V1>\w+)_V3-(?P<V3>\d+)_VA-(?P<VA>\d+)_VB-(?P<VB>\d+)_VC-(?P<VC>\d+)"
)
CLAVE = ("V1", "V3", "VA", "VB", "VC")


def leer_declaradas():
    """celdas_declaradas.csv -> {(V1,V3,VA,VB,VC): motivo}."""
    f = base_dir / "celdas_declaradas.csv"
    if not f.exists():
        return {}
    # Las lineas que empiezan con # son comentarios: csv no los filtra solo.
    lineas = [ln for ln in f.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return {
        tuple(fila[c] for c in CLAVE): fila["motivo"]
        for fila in csv.DictReader(lineas)
    }


def leer_medidas():
    """results/*.json de esta matriz -> {(V1,V3,VA,VB,VC): metricas}."""
    medidas = {}
    for f in sorted(res_dir.glob("*.json")):
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


def fila_medida(clave, metrics):
    lat = metrics.get("job_latency", {})
    err = metrics.get("job_errors", {}).get("value", 0.0)
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
        "slo_ok": "si" if p95 < SLO_P95_S and err < SLO_ERR else "no",
        "cuello_de_botella": "",
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
with open(res_dir / "summary.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
(res_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

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
