"""Junta los JSON de results/ en results/summary.csv y results/summary.md.
La columna `cuello_de_botella` se completa a mano mirando Grafana durante la corrida."""
import csv
import json
import os
import re
from pathlib import Path

SLO_P95_S = float(os.getenv("SLO_P95_S", "10"))
SLO_ERR = float(os.getenv("SLO_ERR", "0.05"))
res_dir = Path(__file__).with_name("results")
pattern = re.compile(r"(?P<matrix>\w+?)_V1-(?P<V1>\w+)_V3-(?P<V3>\d+)_VA-(?P<VA>\d+)_VB-(?P<VB>\d+)_VC-(?P<VC>\d+)")

rows = []
for f in sorted(res_dir.glob("*.json")):
    m = pattern.match(f.stem)
    if not m:
        continue
    metrics = json.loads(f.read_text())["metrics"]
    lat = metrics.get("job_latency", {})
    err = metrics.get("job_errors", {}).get("value", 0.0)
    done = lat.get("count", 0)
    p95 = lat.get("p(95)", float("nan")) / 1000
    rows.append({
        **m.groupdict(),
        "p50_s": round(lat.get("med", float("nan")) / 1000, 3),
        "p95_s": round(p95, 3),
        "p99_s": round(lat.get("p(99)", float("nan")) / 1000, 3),
        "jobs_ok": done,
        "throughput_req_s": round(metrics.get("http_reqs", {}).get("rate", 0.0), 2),
        "tasa_error": round(err, 4),
        "dlq": metrics.get("job_dlq", {}).get("count", 0),
        "timeouts": metrics.get("job_timeouts", {}).get("count", 0),
        "invalidos_rechazados": metrics.get("invalid_rejected", {}).get("count", 0),
        "slo_ok": "si" if p95 < SLO_P95_S and err < SLO_ERR else "no",
        "cuello_de_botella": "",
    })

if rows:
    with open(res_dir / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    cols = list(rows[0])
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    (res_dir / "summary.md").write_text("\n".join(md) + "\n")
print(f"{len(rows)} celdas resumidas en {res_dir}")
