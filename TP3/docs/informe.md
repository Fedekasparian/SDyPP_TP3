# Informe TP3: Kubernetes, RabbitMQ y Cloud Computing

**SDyPP 2026, UNLu.** Integrantes: _(completar)_
**Responsable de la integración del informe: D** (cada integrante escribe su sección)

## 1. Introducción y arquitectura
Ver [arquitectura.md](arquitectura.md). _(resumen)_

## 2. Hit #0: patrones de mensajería (A)
_(resumen de ex1 a ex5 y lecciones aprendidas)_

## 3. Hit #1: Sobel centralizado, distribuido y tolerante a fallos (A)
- Tiempos de la etapa 1 frente a la etapa 2 según la cantidad de workers.
- Demo de tolerancia a fallos.

## 4. Hit #2: offloading en la nube (C)
- Ciclo provisioning → bootstrap → deploy → join → teardown, con logs y capturas.
- Arquitectura híbrida y justificación local o nube.
- Remote state y pipeline plan/apply.

## 5. Hit #3: plataforma en GKE (B y C)
- Nodepools, workers fuera del cluster, DLQ, retry y fanout.
- Pipelines 1.1 a 1.N y pipeline 2.

### Plataforma de aplicación (B)

La API valida antes de encolar y conserva estado en Redis. Cada request verifica un Bearer firmado con HMAC-SHA256, lo que permite usar cualquier réplica sin afinidad. Las llamadas bloqueantes de Redis/pika y el procesamiento de validación se ejecutan fuera del event loop. El consumidor del fanout guarda progreso en un Redis Stream con TTL; el frontend recibe snapshots mediante SSE y ofrece estadísticas para admin.

La validación local incluye 58 pruebas (13 de integración con servicios reales), igualdad del resultado distribuido con el cálculo centralizado y evidencia R4 con tres backends. La ejecución R4 en GKE queda pendiente del despliegue de C. Detalles y límites: [parte-b.md](parte-b.md).

## 6. Hit #4: observabilidad (D)

### 6.1 Qué se instrumentó y por qué

El stack es **Prometheus 2.54.1 + Grafana 11.2.0**. En Kubernetes se despliega con
kube-prometheus-stack y `ServiceMonitor`s; en docker-compose, con el perfil `obs`
(`docker compose --profile obs up -d`). Prometheus raspa tres jobs:

| Job | De dónde | Qué aporta |
|---|---|---|
| `backend` | `backend:8000/metrics` | Latencia y códigos HTTP de la API, tareas encoladas. |
| `consumers` | descubrimiento por DNS sobre `worker`, `split`, `joiner`, `dlq-monitor`, puerto 8080 | Tareas procesadas y errores **por servicio**. Al ser DNS, un `--scale worker=6` aparece solo: no hay que tocar la configuración. |
| `rabbitmq` | `rabbitmq:15692/metrics` | Profundidad **por cola**, publicados y consumidos. |

Las métricas propias (`tasks_queued`, `tasks_processed_total`, `task_errors_total`
y los histogramas de latencia) están en [`tp3common/metrics.py`](../services/tp3common/metrics.py).

Dos decisiones de instrumentación que vale la pena justificar:

- **Métricas de RabbitMQ por cola, no solo globales.** El plugin
  `rabbitmq_prometheus` publica por defecto únicamente agregados
  (`rabbitmq_global_messages_*`). Con eso no se puede distinguir si los mensajes
  esperando están en `tasks.tp3-worker` (trabajo pendiente, normal) o en
  `tasks.parked` (fragmentos que agotaron sus reintentos, grave). Se activó
  `prometheus.return_per_object_metrics = true`
  ([`observability/rabbitmq/prometheus.conf`](../observability/rabbitmq/prometheus.conf)),
  que agrega las series por cola. El costo es cardinalidad; con las ~6 colas del
  TP es despreciable.
- **Descubrimiento por DNS para los consumidores.** Es lo que permite que la
  variable V3 de la matriz (cantidad de workers) se mueva entre 1 y 8 sin
  reconfigurar Prometheus.

### 6.2 El dashboard

Dashboard *TP3 - Sobel distribuido* (uid `tp3-main`), provisionado desde
[`observability/dashboards/tp3.json`](../observability/dashboards/tp3.json), con
10 paneles. Capturas en [`evidencia/hit4/`](../evidencia/hit4/), tomadas durante
la corrida real de la matriz R5:

| Captura | Panel |
|---|---|
| `rabbitmq_mensajes_en_cola.png` | Mensajes en cola, por cola |
| `rabbitmq_publicados_consumidos.png` | Publicados y consumidos (msg/s) |
| `latencia_p50_p95_p99.png` | Latencia HTTP del backend |
| `throughput.png` | Throughput en tareas/s por servicio |

Lo que muestran, que es lo que importa:

- La cola `tasks.tp3-worker` dibuja un **diente de sierra**: cada celda de k6
  publica su ráfaga y los workers la drenan antes de la siguiente. Los picos
  crecen de ~150 a ~1.800 y hasta ~6.500 mensajes cuando la matriz llega a las
  celdas de VA=50, donde cada request genera 50 imágenes × 4 fragmentos.
- **Publicados y consumidos van casi superpuestos** (~400 msg/s). Es la
  observación central del hit: lo que crece bajo carga es la *profundidad
  instantánea* de la cola, no un atraso acumulado. Los workers sostienen el
  ritmo de publicación.
- `tasks.parked` y `tasks.dlq` quedan planas en cero durante toda la matriz:
  ningún fragmento agotó sus reintentos en condiciones normales. Los escenarios
  de DLQ hubo que **forzarlos** (sección 6.4).
- En throughput, `split` queda en ~20 tareas/s contra ~150 de los demás. No es
  un cuello de botella: `split` procesa un mensaje por request, mientras que
  worker, joiner y dlq-monitor procesan uno por fragmento.

### 6.3 Limitación declarada: CPU y memoria por pod y por nodo

Los paneles 1 a 4 (*CPU por pod*, *Memoria por pod*, *CPU por nodo*, *Memoria por
nodo*) aparecen en **"No data"** en las capturas. No es un error del dashboard:
esas series provienen de **cAdvisor** y **node-exporter**, que forman parte de
kube-prometheus-stack y **solo existen dentro de un cluster de Kubernetes**. En
docker-compose no hay pods ni nodos que medir, así que las consultas no devuelven
series.

Las queries quedaron escritas y validadas contra el esquema de
kube-prometheus-stack: el dashboard se puebla solo al desplegarlo sobre el
cluster, sin cambiarle nada.

### 6.4 La alerta disparada

_(pendiente: capturas y registro de la transición `inactive -> pending -> firing`,
que produce `scripts/evidencia_hit4_r5.sh` en
`evidencia/hit4/alertas_transicion.log`.)_

Las cuatro alertas están en dos formatos, porque los consume software distinto:
[`alerts.yaml`](../observability/alerts.yaml) es un `PrometheusRule`, un objeto
de Kubernetes que solo entiende el Prometheus Operator, y
[`alerts-compose.yml`](../observability/alerts-compose.yml) es el formato nativo
que carga `rule_files` en docker-compose. El contenido de `groups:` es idéntico;
un `PrometheusRule` no es más que ese bloque envuelto en metadata de k8s. **Si se
cambia una alerta hay que cambiarla en los dos archivos.**

| Alerta | Condición | Espera | Severidad |
|---|---|---|---|
| `ColaDeTareasAlta` | más de 100 fragmentos esperando en una cola `tasks.tp3-*` | 2 min | warning |
| `WorkersSinProcesar` | hay tareas en cola y ningún worker procesó en 2 min | 1 min | critical |
| `FragmentosEstacionadosEnDLQ` | algo en `tasks.parked` | 1 min | warning |
| `TasaDeErroresAlta` | más del 5 % de las tareas falla | 5 min | warning |

Que las cuatro aparezcan listadas en `/alerts` como `Inactive` ya es la
verificación de que `rule_files` quedó bien cargado: antes de este trabajo
`prometheus-compose.yml` tenía `rule_files: []` y ninguna alerta podía dispararse
en local.


## 7. Requisitos R1 a R5
| Req. | Evidencia | Dónde |
|---|---|---|
| R1 | Captura de `ImagePullBackOff` y del pull exitoso | [r1-evidencia.md](r1-evidencia.md) |
| R2 | Requests inválidos devuelven 400 y la cola no cambia | video, logs |
| R3 | [contrato.md](contrato.md) | |
| R4 | 13 verificaciones locales, tres backends distintos; GKE pendiente | [r4_local.txt](../evidencia/r4_local.txt), [parte B](parte-b.md) |
| R5 | Matriz completa | sección 8 |

## 8. Análisis de desempeño (D)

### 8.1 Cómo se midió

La carga la genera **k6 0.54.0**, corriendo como contenedor (`grafana/k6:0.54.0`)
dentro de la red de compose, contra `http://backend:8000`. El escenario está en
[`loadtest/k6/job.js`](../loadtest/k6/job.js) y el barrido en
[`loadtest/run_matrix.sh`](../loadtest/run_matrix.sh).

**Qué mide cada métrica.** Es la distinción más importante del capítulo y conviene
fijarla antes de mirar ninguna tabla:

| Métrica | Qué mide | Dónde se ve |
|---|---|---|
| `http_req_duration` | Tiempo de **aceptar** el request (`POST /jobs` devuelve 202 y encola). | Panel "Latencia HTTP backend" |
| `job_latency` | Tiempo **end-to-end**: desde que se sube la imagen hasta que el job figura `done`, incluyendo split, procesamiento de todos los fragmentos y joiner. | Columnas `p50_s`, `p95_s`, `p99_s` de la matriz |

El SLO del TP se evalúa sobre `job_latency`, no sobre la latencia HTTP: un
backend que acepta en 10 ms pero tarda 40 s en devolver la imagen no cumple nada.
La latencia HTTP baja es, de hecho, la prueba de que el desacoplamiento por cola
funciona: el backend no se bloquea esperando a los workers.

**Perfil de cada celda.** Ejecutor `ramping-vus`, con tres tramos:

| Tramo | Duración | Para qué |
|---|---|---|
| Ramp-up | 5 s | Llegar a VC usuarios sin golpear el sistema de cero a todo. |
| Meseta | **20 s** | El tramo que se mide. |
| Ramp-down | 5 s | Cerrar sin cortar jobs en vuelo. |

**Por qué la meseta es de 20 s y no de 60.** La matriz tiene 108 celdas
obligatorias, porque la consigna exige el producto cruzado completo
VA × VB × VC × 2 valores de V1 × 2 de V3. Con la meseta de 60 s del default, el
barrido completo da unas 2 h 15 de corrida. El recorte se hizo **acortando la
meseta, nunca sacando celdas**: una matriz de 108 celdas de 20 s describe el
mismo espacio de parámetros que una de 60 s, con menos muestras por celda; una
matriz de 40 celdas de 60 s ya no responde la pregunta que se hizo. La
contrapartida honesta es que en las celdas de baja concurrencia (VC=1) la meseta
de 20 s deja pocas muestras, y ahí los percentiles p99 hay que leerlos con
reservas: con 9 jobs completados, el p99 **es** el máximo.

**Parámetros fijos en todas las celdas:**

- `INVALID_RATE=0.05`: el 5% de los requests manda un archivo corrupto a
  propósito. Sirve para verificar en caliente el requisito R2 (debe responder
  400 sin tocar la cola) y queda contado en `invalidos_rechazados`.
- `TIMEOUT_S=30`: espera máxima por job. Pasado ese tiempo el job cuenta como
  `timeout` y como error. Ver 8.4.
- Un usuario virtual adicional **sin token** en cada celda, que debe recibir 401.
  Es la verificación continua de que la autenticación no se cae bajo carga.

**Entorno.** Todo corre en una única máquina (Windows 11, 13,8 GB de RAM, Docker
Desktop con backend WSL2): backend, RabbitMQ, Redis, los workers, Prometheus,
Grafana y el propio k6. **Esto no es un cluster y los números no son de
producción**: miden el comportamiento relativo entre configuraciones, que es lo
que la matriz pregunta, no el techo absoluto del sistema. La consecuencia
concreta de ese límite está en 8.5.

### 8.2 La matriz

La tabla completa de las **108 celdas** está en
[`loadtest/results/summary.md`](../loadtest/results/summary.md) y en
`summary.csv`, con las columnas `p50_s`, `p95_s`, `p99_s`, `jobs_ok`,
`throughput_req_s`, `tasa_error`, `dlq`, `timeouts`, `invalidos_rechazados`,
`slo_ok` y `cuello_de_botella`. Aquí se analizan los agregados; la tabla cruda no
se reproduce porque 108 filas no se leen.

El resumen **siempre emite las 108 filas esperadas**, aunque falte el resultado
de alguna. Cada fila sale como `medida`, con un motivo declarado, o como
`SIN MEDIR`. La razón es que R5 es un entregable que no admite huecos: si solo se
listaran los archivos existentes, una celda cortada desaparecería de la tabla sin
que nada lo señale.

### 8.3 Qué variable domina el desempeño

La matriz permite aislar el efecto de cada variable manteniendo las otras fijas.
El resultado es contraintuitivo y es el hallazgo principal del trabajo.

**V3 (cantidad de workers) casi no afecta la latencia.** Comparando pares de
celdas idénticas en todo salvo V3, al pasar de 2 a 6 workers:

| | |
|---|---|
| Pares comparados | 31 |
| Cambio **mediano** de p95 | **−1,0 %** |
| Pares donde 6 workers mejoró (>5 %) | 13 |
| Pares donde quedó igual (±5 %) | 5 |
| Pares donde 6 workers **empeoró** (>5 %) | 13 |

Triplicar la cantidad de workers no mejora el sistema: la mitad de los casos
mejora, la otra mitad empeora, y la mediana es indistinguible de cero.

**Por qué.** Todo el stack corre en una sola máquina de **8 núcleos lógicos**,
compartidos entre el backend, RabbitMQ, Redis, split, joiner, dlq-monitor,
Prometheus, Grafana, los workers y el propio generador de carga. Sumar
contenedores de worker no agrega capacidad de cómputo: **reparte los mismos
núcleos entre más procesos**, y agrega contención de CPU y de conexiones a
RabbitMQ. En los casos de más carga (VA=10, VC=50) el efecto es claramente
negativo: con 2 workers se completaron 150 jobs y con 6 apenas 58.

Esto **no contradice** el diseño distribuido: lo confirma por el lado opuesto.
El escalado horizontal rinde cuando cada réplica suma recursos propios, es decir
cuando los workers caen en nodos distintos. Medido en una sola máquina, V3 no
mide elasticidad: mide contención. La verificación correcta del escalado es la
del Hit #1 y la del despliegue en GKE, donde los workers corren fuera del
cluster y en VMs separadas.

**Las variables que sí dominan son VA y VC**, es decir el tamaño del lote y la
concurrencia:

| Variable | p95 mediana | Celdas que cumplen el SLO |
|---|---|---|
| VA=1 | 1,86 s | 28/28 |
| VA=10 | 3,04 s | 12/18 |
| VA=50 | 14,81 s | 3/18 |
| VC=1 | 1,09 s | 20/23 |
| VC=10 | 3,33 s | 17/23 |
| VC=50 | 14,91 s | 6/18 |

Ambas multiplican la cantidad de fragmentos en vuelo: VA por archivo subido y VC
por usuario simultáneo. Cada imagen genera 4 fragmentos, así que una celda
VA=50 / VC=50 pone 10.000 fragmentos en la cola.

**VB (operaciones encadenadas) casi no influye**: la p95 mediana va de 2,53 s con
una operación a 3,09 s con tres. Encadenar grayscale + blur + sobel cuesta un 22 %
más de latencia, no el triple. El procesamiento por fragmento no es el costo
dominante: lo es el recorrido del fragmento por la cola y el almacenamiento.

**Conclusión del análisis.** El cuello de botella de esta implementación **no
está en el cómputo de Sobel** sino en el camino de cada fragmento: encolado,
transferencia y persistencia en Redis. Por eso agregar workers no ayuda y
agregar operaciones por fragmento cuesta poco, mientras que multiplicar la
cantidad de fragmentos degrada la latencia de forma inmediata.

### 8.4 Casos inválidos y fallidos

_(pendiente: se completa con la salida de `scripts/evidencia_hit4_r5.sh`, que
produce los tres escenarios de falla de R5 y el conteo de errores claros,
fragmentos en DLQ y reprocesados.)_


### 8.5 Límites del entorno y celdas no medidas

Seis celdas (`V1=1MB`, `VA=50`, `VC=50`, cruzadas con los dos valores de V3 y las
tres cadenas de VB) **no se pudieron medir** y figuran declaradas en la tabla.
El motivo es aritmético: 50 archivos de 1 MB por request con 50 usuarios
concurrentes son **2,5 GB de cuerpos de request en vuelo**, contra ~2 GB de RAM
libre en la máquina de pruebas. El primer intento no solo falló: agotó la memoria
de la VM de Docker y dejó al motor devolviendo error 500 en todas sus llamadas,
obligando a reiniciar Docker Desktop.

A partir de ese episodio el generador de carga corre con un **techo de memoria**
(`--memory`), de modo que una celda que no entra muere sola y el resto de la
matriz sobrevive. Es la diferencia entre perder una celda y perder la corrida.

**Un hallazgo del entorno que vale como observación de diseño.** Durante el
barrido, Redis llegó a **2,91 GB con 602.484 claves**. No es una fuga: los
fragmentos tienen TTL de 24 horas (`JOB_TTL_S` en
[`tp3common/store.py`](../services/common/tp3common/store.py)). Pero el TTL es
irrelevante dentro de una sesión de pruebas: **nada expira mientras se mide**, y
como los bytes de cada fragmento (`:in` y `:out`) viven en Redis, la memoria
crece con el *throughput acumulado*, no con los jobs simultáneos. A las ~150
tareas/s medidas, eso son gigabytes por hora.

La consecuencia es concreta y explica los resultados de 8.3: los fragmentos
intermedios **dejan de ser útiles apenas el joiner arma la imagen final**, pero
siguen ocupando memoria durante 24 horas. Dos mejoras se desprenden:

1. Borrar los fragmentos `:in`/`:out` al completarse el job, o darles un TTL
   corto propio, distinto del TTL del resultado final.
2. Mover los blobs a almacenamiento de objetos y dejar en Redis solo los punteros
   y el estado. Redis como *store* de imágenes es lo que hace que el camino del
   fragmento domine el costo.

## 9. Marco conceptual

### 9.1 NIST SP 800-145: las cinco características esenciales

La definición del NIST (SP 800-145) enumera cinco características que un sistema
debe exhibir para considerarse cloud computing. El TP las cumple de forma
desigual, y vale la pena decir dónde sí y dónde no:

| Característica | Cómo la cumple el sistema | Grado |
|---|---|---|
| **Autoservicio bajo demanda** | El usuario sube imágenes por `POST /jobs` y obtiene un `job_id` sin que ningún operador intervenga. El alta de credenciales es `POST /admin/tokens`. | Completo |
| **Acceso amplio por red** | API HTTP estándar, consumible desde el frontend web, `curl` o k6, sin cliente propietario. | Completo |
| **Pooling de recursos** | Los workers son intercambiables y toman fragmentos de una cola compartida: ningún usuario tiene un worker asignado. El multi-tenancy es por token, y los resultados se aíslan por `job_id`. | Completo |
| **Elasticidad rápida** | `--scale worker=N` en compose y `kubectl scale deploy/worker` en Kubernetes. Es elasticidad **manual**: no hay HPA ni métrica de autoescalado conectada. | Parcial |
| **Servicio medido** | Es justamente lo que agrega el Hit #4: Prometheus mide tareas por servicio, profundidad de cola, latencia y errores, y Grafana los expone. Falta el paso de convertir esa medición en facturación o cuotas por tenant. | Parcial |

La conclusión honesta es que el sistema es **cloud-native en arquitectura pero no
en operación**: tiene las propiedades estructurales (servicios sin estado,
desacoplamiento por cola, escalado horizontal) pero la elasticidad la dispara una
persona, no una política.

### 9.2 Cloud native, híbrido, cloud-bursting y offloading

- **Cloud native** describe un sistema diseñado para la nube desde el principio:
  procesos sin estado, configuración por entorno, escalado horizontal,
  tolerancia a que cualquier instancia desaparezca. Nuestros workers lo son: no
  guardan nada entre fragmentos, y si uno muere su fragmento vuelve a la cola.
- **Híbrido** es ejecutar parte del sistema en infraestructura propia y parte en
  la nube, de forma permanente. En el TP aparece cuando los workers corren fuera
  del cluster de GKE mientras el backend y RabbitMQ viven adentro.
- **Cloud-bursting** es un caso particular de híbrido, pero **temporal y
  disparado por demanda**: la carga base corre on-premise y solo los picos
  desbordan a la nube. La diferencia con el híbrido permanente es el disparador,
  no la topología.
- **Offloading** es delegar un trabajo concreto a otro lado porque allá se hace
  mejor o más barato, sin que eso implique un pico. Sobel sobre una imagen de
  100 MB es el ejemplo: el cliente no la procesa, la manda.

La distinción que suele pedirse en el oral es entre las dos últimas:
**bursting es por capacidad y es elástico; offloading es por capacidad de cómputo
o costo y es estructural.**

### 9.3 CAP: qué elige cada pieza de la arquitectura

El teorema CAP dice que ante una **partición de red** (P) un sistema distribuido
debe sacrificar consistencia (C) o disponibilidad (A). Es importante no leerlo
como "elegí dos de tres": sin partición no hay que sacrificar nada, y la
partición no se elige, se sufre. La pregunta real es **cómo se comporta cada
componente cuando la partición ocurre**.

**RabbitMQ: no todas las colas eligen lo mismo.** Conviene mirar la topología real
([`tp3common/rabbit.py`](../services/common/tp3common/rabbit.py)) antes de
afirmar nada, porque el sistema usa **dos tipos de cola distintos**:

| Cola | Tipo | Comportamiento ante partición |
|---|---|---|
| `tasks.tp3-worker` (y una por pool) | **quorum** | Replicada por **Raft**. Toda escritura necesita la mayoría de las réplicas; el lado minoritario deja de aceptar publicaciones y consumos. **CP.** |
| `split.requests`, `results.joiner`, `results.monitor`, `tasks.dlq`, `tasks.parked` | **classic** | Sin replicar: viven en un solo nodo del cluster. Si ese nodo queda del otro lado de la partición, la cola es simplemente **inalcanzable**. |

Las colas de tareas llevan además `x-delivery-limit: 2` y un dead-letter
exchange: si un worker muere con el mensaje sin confirmar, RabbitMQ lo
reentrega, y superado el límite el fragmento va a la DLQ en lugar de ciclar para
siempre. Todos los mensajes se publican con `delivery_mode=2` (persistentes).

La elección es coherente con el criterio de "CP donde el error es irreparable":
**la cola por la que pasa cada fragmento —la única cuya pérdida rompe un job— es
la replicada.** Las de resultados y las de requests son reconstruibles o
reintentables.

**Una observación que surge de mirar esto y que vale como mejora propuesta:**
`tasks.parked` es **classic**. Es la cola donde terminan los fragmentos que ya
agotaron sus reintentos, es decir **los que más trabajo acumulado tienen
encima** y los que requieren intervención manual (`POST /admin/dlq/reprocess`).
Perder esa cola significa perder justamente los casos que no se pueden
reconstruir solos. Declararla `quorum` cuesta lo mismo que las otras y es el
cambio de una línea; queda anotado como trabajo futuro.

**Redis con réplica asincrónica → AP.** El primario confirma la escritura al
cliente **antes** de que la réplica la reciba. Ante una partición, el primario
del lado minoritario sigue aceptando escrituras, y si Sentinel promueve a la
réplica del otro lado, todo lo confirmado y no replicado **se pierde al
reconciliar**. Se conserva la disponibilidad y se sacrifica la consistencia.

**Qué implica para nuestra arquitectura.** Las dos piezas guardan cosas
distintas y por eso la elección opuesta no es incoherente:

- RabbitMQ transporta los **fragmentos**, que no se pueden perder: si un
  fragmento desaparece, el joiner espera para siempre y el job queda colgado.
  Que RabbitMQ se vuelva indisponible ante una partición es el comportamiento
  deseable: el sistema se frena y retoma, en vez de entregar una imagen
  incompleta.
- Redis guarda el **estado del job y los resultados parciales**. Perder una
  escritura reciente ahí significa que un fragmento ya procesado figure como
  pendiente. El daño es reprocesarlo, no corromper la salida, porque la
  operación es idempotente: aplicar Sobel dos veces al mismo fragmento da el
  mismo resultado.

Dicho de otra forma: **pusimos la pieza CP donde un error es irreparable y la
pieza AP donde un error solo cuesta trabajo repetido.** Ese es el criterio con
el que conviene defender la decisión, y no "RabbitMQ es CP y Redis es AP"
a secas.

Una aclaración que suele faltar: la elección de Redis en este TP es
**standalone en docker-compose**, es decir sin réplica y sin Sentinel. En esa
configuración no hay partición posible dentro de Redis — hay un solo nodo —, así
que CAP no aplica: lo que hay es un **punto único de falla**. El análisis de
arriba describe lo que pasaría al llevarlo a una topología replicada, que es el
paso natural si el sistema fuera a producción.

## 10. Uso de herramientas de IA

| Integrante | Herramienta | Para qué la usó | Qué hubo que corregir |
|---|---|---|---|
| D (Agustina) | Claude Code | Correr la matriz R5, armar la evidencia del Hit #4 y redactar las secciones 6, 8, 9 y 11. | Ver el detalle abajo: tres errores de fondo en el andamiaje generado, encontrados al ejecutarlo. |
| A | _(completar)_ | | |
| B | _(completar)_ | | |
| C | _(completar)_ | | |

### 10.1 Qué falló del código generado y cómo se detectó

El andamiaje de la parte D (dashboard, alertas, escenario de k6, script de
barrido) se generó con asistencia de IA y **no funcionó tal como fue entregado**.
Los tres errores salieron al ejecutarlo, no al leerlo, y ninguno daba un mensaje
que apuntara a su causa:

1. **Ruta equivocada al escalar workers.** El script calculaba la raíz del repo
   con `cd ../../..`, un nivel de más desde `TP3/loadtest/`. Caía en una carpeta
   sin `docker-compose.yml` y moría en la primera celda con
   `no configuration file provided`. Se reemplazó por un `REPO_ROOT` calculado
   una sola vez.
2. **Colisión de nombres entre la corrida de humo y la matriz real.** El modo de
   humo guardaba sus resultados con el mismo nombre de celda que la matriz
   definitiva. Como el script saltea toda celda que ya tenga archivo, 8 de las
   108 celdas de R5 habrían quedado medidas con la meseta corta del humo (10 s)
   en vez de la real (20 s), **sin ningún aviso**. Se le dio al humo un prefijo
   propio y se filtró por matriz al resumir.
3. **Celdas saturadas que desaparecían de la tabla.** El escenario esperaba
   hasta 120 s por job y el barrido cortaba la celda a los 300 s: una celda
   saturada se moría antes de escribir su resultado y dejaba un hueco silencioso
   en la matriz. Se expuso ese tiempo como parámetro y se redujo, de modo que la
   celda **termina** y reporta sus timeouts, que es un dato válido, en lugar de
   desaparecer.

La lección transferible es que los tres fallos comparten la misma forma: **el
código corría sin error visible y producía resultados plausibles pero
incorrectos.** Revisar la salida no alcanzaba; hubo que ejecutar, comparar contra
lo que debía pasar y desconfiar de los silencios. De ahí que `summarize.py` se
reescribiera para emitir siempre las 108 filas esperadas y marcar `SIN MEDIR` lo
que falte: convierte un hueco silencioso en una fila visible.

## 11. Conclusiones

**1. El cuello de botella no está donde parecía.** La hipótesis natural era que
el costo dominante fuera el cómputo de Sobel, y por lo tanto que agregar workers
mejorara la latencia. La matriz dice lo contrario: encadenar tres operaciones en
vez de una cuesta un 22 % más de latencia, no el triple, mientras que multiplicar
la cantidad de fragmentos (VA o VC) la degrada de inmediato. El costo real es el
**recorrido de cada fragmento** —encolado, transferencia y persistencia en
Redis—, no procesarlo.

**2. Escalar workers en una sola máquina no es escalar.** Triplicar V3 de 2 a 6
dejó la p95 mediana en −1,0 % sobre 31 pares de celdas idénticas, con la mitad de
los casos peor que mejor. Con los 8 núcleos de la máquina compartidos entre todo
el stack, sumar contenedores reparte los mismos recursos y agrega contención. El
diseño distribuido no queda refutado: queda demostrado que **medir elasticidad
exige nodos separados**, que es exactamente lo que aporta el despliegue en GKE.
Es el resultado que más cambia lo que uno escribiría sin medir.

**3. La observabilidad sirvió para operar, no solo para entregar capturas.** Los
paneles de profundidad por cola fueron los que permitieron distinguir "la cola
crece" de "la cola no se drena", y ver que publicados y consumidos iban
superpuestos: el sistema no se atrasaba, acumulaba profundidad instantánea. Sin
las métricas por cola —que hubo que activar explícitamente— esa diferencia no
era visible.

**4. Los errores caros fueron los silenciosos.** De los tres fallos del andamiaje
(sección 10), ninguno se manifestó como un error: el barrido imprimía "sigue" y
continuaba. El más peligroso habría medido 8 de las 108 celdas con una duración
distinta sin avisar. La contramedida que quedó en el repositorio es que el
resumen emita **siempre** las 108 filas y marque `SIN MEDIR` lo que falte:
convierte una ausencia invisible en una fila que salta a la vista. Es la lección
más transferible del trabajo.

**5. Lo que falta y por qué.** Seis celdas de la matriz no se pudieron medir por
la memoria del entorno de pruebas, y quedan declaradas con su motivo en la tabla
en lugar de omitidas. Los paneles de CPU y memoria por pod y por nodo requieren
cAdvisor y node-exporter, que solo existen en Kubernetes. Ambas son limitaciones
del entorno, no del sistema, y están señaladas como tales en las secciones 6.3 y
8.5.

### 11.1 Trabajo futuro

- **Declarar `tasks.parked` como cola quorum.** Hoy es classic: la cola que
  guarda los fragmentos que ya agotaron reintentos es la menos protegida de
  todas (sección 9.3). Es un cambio de una línea.
- **Liberar los fragmentos intermedios al completarse el job**, o darles un TTL
  propio mucho más corto que el del resultado final. Hoy heredan las 24 horas y
  hacen crecer Redis con el throughput acumulado (sección 8.5).
- **Mover los blobs a almacenamiento de objetos**, dejando en Redis solo estado y
  punteros. Ataca directamente el cuello de botella de la conclusión 1.
- **Autoescalado por métrica.** Las métricas para un HPA sobre profundidad de
  cola ya están publicadas; falta conectarlas. Es lo que convertiría la
  elasticidad manual de la sección 9.1 en elasticidad real.
