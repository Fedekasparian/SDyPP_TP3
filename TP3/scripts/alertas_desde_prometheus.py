"""Reconstruye la transicion inactive -> pending -> firing -> inactive desde la
serie ALERTS de Prometheus, sin depender de haber estado mirando en vivo.

POR QUE EXISTE
--------------
`evidencia_hit4_r5.sh` registra el estado de las alertas en vivo, cada 15 s.
Si ese registro falla (o si la corrida ya paso), los datos NO se perdieron:
Prometheus expone la serie sintetica `ALERTS{alertname, alertstate}`, que vale 1
mientras una alerta esta en `pending` o en `firing` y desaparece cuando vuelve a
`inactive`. Con una consulta de rango se reconstruye la misma cronologia, con la
resolucion del scrape y horarios exactos.

USO
    py TP3/scripts/alertas_desde_prometheus.py [minutos_hacia_atras] [salida]

    py TP3/scripts/alertas_desde_prometheus.py 90 TP3/evidencia/hit4/alertas_transicion.log
"""
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

PROM = "http://localhost:9090"
PASO = 15  # segundos; igual al intervalo con que mira el script en vivo


def consultar(minutos: int):
    fin = int(dt.datetime.now().timestamp())
    ini = fin - minutos * 60
    q = urllib.parse.urlencode(
        {"query": "ALERTS", "start": ini, "end": fin, "step": PASO}
    )
    with urllib.request.urlopen(f"{PROM}/api/v1/query_range?{q}", timeout=30) as r:
        return json.load(r)["data"]["result"], ini, fin


def main() -> None:
    minutos = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    salida = sys.argv[2] if len(sys.argv) > 2 else None
    series, ini, fin = consultar(minutos)

    # (instante -> {alerta: estado}). Lo que no aparece en un instante esta inactive.
    por_instante: dict[int, dict[str, str]] = {}
    for s in series:
        nombre = s["metric"].get("alertname", "?")
        estado = s["metric"].get("alertstate", "?")
        for t, _ in s["values"]:
            por_instante.setdefault(int(float(t)), {})[nombre] = estado

    alertas = sorted({s["metric"].get("alertname", "?") for s in series})
    lineas = [
        "# Transicion de alertas reconstruida desde la serie ALERTS de Prometheus.",
        f"# Ventana: {dt.datetime.fromtimestamp(ini):%Y-%m-%d %H:%M:%S}"
        f" a {dt.datetime.fromtimestamp(fin):%H:%M:%S}  (paso {PASO}s)",
        "# Consulta: ALERTS   (vale 1 en pending/firing; ausente = inactive)",
        "# Una alerta que no figura en una linea estaba en inactive en ese instante.",
        "",
    ]
    if not alertas:
        lineas.append("NINGUNA alerta salio de inactive en la ventana consultada.")
    else:
        # Solo los cambios: el muestreo completo son cientos de lineas iguales.
        anterior: dict[str, str] = {}
        for t in sorted(por_instante):
            actual = por_instante[t]
            if actual != anterior:
                hora = dt.datetime.fromtimestamp(t).strftime("%H:%M:%S")
                for a in alertas:
                    estado = actual.get(a, "inactive")
                    previo = anterior.get(a, "inactive")
                    if estado != previo:
                        lineas.append(f"{hora}  {a:32} {previo:8} -> {estado}")
                anterior = actual
        # La serie ALERTS simplemente DEJA de existir cuando la alerta vuelve a
        # inactive, asi que el instante siguiente al ultimo con datos es el
        # momento en que se apago. Sin esta linea el log terminaria mostrando
        # la alerta en firing/pending, que es justo lo contrario de lo que paso.
        ultimo = max(por_instante)
        hora_fin = dt.datetime.fromtimestamp(ultimo + PASO).strftime("%H:%M:%S")
        for a in alertas:
            previo = anterior.get(a, "inactive")
            if previo != "inactive":
                lineas.append(f"{hora_fin}  {a:32} {previo:8} -> inactive")

    texto = "\n".join(lineas) + "\n"
    print(texto, end="")
    if salida:
        with open(salida, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"-> escrito en {salida}")


if __name__ == "__main__":
    main()
