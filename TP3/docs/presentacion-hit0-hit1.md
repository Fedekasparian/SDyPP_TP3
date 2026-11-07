# Guía de presentación: Hit #0 y Hit #1

Paso a paso para la demo en vivo, unos 12 minutos. Los comandos se probaron el 23/10/2026 en
Git Bash (Windows) desde la raíz del repo, con el stack de 3 backends levantado. Las salidas que
figuran abajo son de esa prueba.

## Antes de presentar (5 min antes, sin público)

1. Levantar el stack si no está arriba:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.r4.yml --profile obs up -d --scale worker=3
   curl -s localhost:8081/api/health      # {"backend":"ok","redis":"ok","rabbitmq":"ok"}
   ```
   Con 3 backends **no se publica el puerto 8000**: todo entra por `localhost:8081/api`.
2. Dejar dos terminales: **T1** para correr comandos y **T2** para logs.
3. Correr el Hit #0 una vez, para que quede la imagen cacheada (la primera vez construye la
   imagen de los ejemplos y baja RabbitMQ):
   ```bash
   bash TP3/queue/run_demo.sh ex1
   ```
4. Abrir en el navegador:
   - RabbitMQ: http://localhost:15672 (usuario y contraseña del `.env`)
   - [queue/ex5/README.md](../queue/ex5/README.md) y [hit1/README.md](../hit1/README.md), que tienen los diagramas.

---

## Parte 1: Hit #0, patrones de mensajería (~6 min)

**Para abrir (20 s):**
> "Antes de armar el sistema de Sobel probamos por separado los cuatro patrones de RabbitMQ que
> después usa la app: cola de trabajo, pub/sub, DLQ y retry con backoff. Cada uno tiene su código
> Python, los manifiestos de Kubernetes y un README. El script `run_demo.sh` levanta un RabbitMQ
> aparte y corre cada escenario."

`run_demo.sh` usa su propio RabbitMQ en la red `hit0`, así que no toca el stack principal.

### Paso 1. ex1, cola de trabajo
```bash
bash TP3/queue/run_demo.sh ex1
```
- Con 1 consumidor, recibe las tareas 1 a 10 en orden.
- Con 2 consumidores (A tarda 1 s y B tarda 0,1 s) y **sin prefetch**, se reparten 5 y 5:
  RabbitMQ hace round-robin a ciegas, sin mirar si A está ocupado.
- Con **`prefetch=1`**, B se lleva casi todas: RabbitMQ no le manda otra tarea a nadie hasta que
  confirma (ack) la anterior.

> "Por eso en la app los workers usan `prefetch=1`: si no, sumar workers no mejora nada cuando
> hay uno lento."

### Paso 2. ex2, pub/sub (fanout)
```bash
bash TP3/queue/run_demo.sh ex2
```
- Los 3 nodos reciben los mismos 5 bloques: **señalar el digest igual** (`578c788036578a18`) en los tres.
- El **nodo tardío** solo recibe los bloques 4 y 5.

> "El fanout copia el mensaje a cada cola, pero no guarda nada. El que se suscribe tarde se
> pierde lo anterior. Kafka o Google Pub/Sub sí retienen y dejan releer."

### Paso 3. ex3, Dead Letter Queue
```bash
bash TP3/queue/run_demo.sh ex3
```
- Los mensajes 3, 6 y 9 traen `"error": true`. El consumidor les hace `nack` y aparecen en la DLQ
  con `motivo=rejected, cola origen=ex3.main`.

> "Sin DLQ, un mensaje que siempre falla o da vueltas para siempre o se pierde. La DLQ lo aparta,
> guarda el motivo y permite reprocesarlo."

### Paso 4. ex4, retry con backoff
```bash
bash TP3/queue/run_demo.sh ex4
```
- **Señalar las horas del log:** los reintentos van a 1, 2, 4 y 8 s.
- El trabajo 1 falla 5 veces, agota los 4 reintentos y va a la DLQ de ex3 con `reintentos=4`.
  El 2 se salva justo en el 5.º intento (con `SEED=7` la corrida es reproducible).

> "Usamos una cola de espera por cada tiempo, con TTL fijo, porque RabbitMQ solo vence el mensaje
> que está primero en la cola. Con una sola cola, uno que espera 8 s trabaría a uno que espera 1 s."

### Paso 5. ex5 y cómo lo usa la app (1 min)
Mostrar la tabla comparativa y el diagrama final de [ex5/README.md](../queue/ex5/README.md), y
después la UI de RabbitMQ del stack real (pestaña *Queues*):
- `tasks.tp3-worker`: **cola de trabajo**, de tipo quorum, con `prefetch=1` en los workers.
- Exchange `results`: **fanout** que avisa al joiner y al monitor.
- `tasks.dlq`: la **DLQ**.
- dlq-monitor: hace el **retry**; después de 3 intentos (`MAX_RETRIES`) manda el fragmento a `tasks.parked`.

---

## Parte 2: Hit #1, Sobel (~6 min)

**Para abrir (20 s):**
> "Sobel calcula el gradiente de cada píxel con dos máscaras de 3×3. Lo hicimos en tres etapas:
> centralizado, distribuido con master-worker y tolerante a fallas. Las tres usan la misma función
> de Sobel, así que las diferencias de tiempo son de arquitectura, no del algoritmo."

### Paso 6. Etapa 1, centralizado
```bash
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "$(pwd -W)/TP3:/tp3" worker \
  python /tp3/hit1/etapa1/sobel_local.py /tp3/loadtest/images/10MB.png /tmp/out.png
```
Salida del ensayo: `leer 0.257s, sobel 0.201s, escribir 0.521s`, o sea **~1 s en total**.

> "El cálculo de Sobel es la parte chica. Leer y escribir el PNG pesan más que calcular."

### Paso 7. Etapa 2, distribuido (master-worker)
Mostrar primero el diagrama de [hit1/README.md](../hit1/README.md): **split** (master) → cola →
**N workers** → fanout → **joiner**. Después:
```bash
BASE_URL=http://localhost:8081/api bash TP3/hit1/bench_distribuido.sh bench
```
Salida del ensayo:
```
workers  split    queue    processing  join     total
1        0.8572   0.0309   0.9329      0.8747   3.8219
2        1.1237   0.0098   0.6818      0.9366   2.8881
4        0.66     0.0082   0.3186      0.585    1.5812
```
- La columna **processing escala**: baja de 0,93 s a 0,32 s con 4 workers. Más allá de 4 no mejora,
  porque la imagen se parte en 4 franjas (`FRAGMENTS_PER_IMAGE`).
- Pero **el total distribuido (1,6 s) es peor que el centralizado (~1 s)**: partir, unir y mover la
  imagen por Redis cuesta más que el Sobel.

> "Sobel es barato por píxel, así que para 10 MB no se amortiza la comunicación. Distribuir
> conviene con imágenes grandes, cadenas largas de operaciones o muchos jobs a la vez. Ahí la
> ganancia es de throughput, y eso lo medimos en el Hit #3."

**Si pregunta por el solapamiento:**
> "Cada franja lleva 1 fila extra arriba y abajo por cada operación de 3×3. Sin eso, los píxeles
> del borde no tienen a sus vecinos reales y aparece una línea negra en cada corte. Un test verifica
> que partir, procesar y unir da exactamente lo mismo que procesar la imagen entera."

### Paso 8. Etapa 3, tolerancia a fallas (el momento fuerte)
En **T2**: `docker compose logs -f worker`

En **T1**:
```bash
BASE_URL=http://localhost:8081/api bash TP3/hit1/bench_distribuido.sh fallas
```
Salida del ensayo:
```
worker /sdypp_tp3-worker-2 (6f859c2b1c6d) muerto con SIGKILL
{"status":"done","fragments":{"total":4,"done":4}, ...}
worker-1 | frag=0-1 ok en 0.708s (intento 0)
worker-1 | frag=0-0 ok en 1.082s (intento 0, reentregado)
worker-1 | frag=0-2 ok en 0.633s (intento 0)
worker-1 | frag=0-3 ok en 0.575s (intento 0)
```
- worker-2 había tomado el fragmento `0-0` y lo matamos con `SIGKILL` (un crash real) antes de que confirmara.
- RabbitMQ vio caerse la conexión y **le reentregó ese fragmento a worker-1**: es el `reentregado` del log.
- El job terminó `done` con 4 de 4 fragmentos, y el cliente no notó nada.

> "Lo que reasigna es RabbitMQ, porque tiene el mensaje sin confirmar. Lo logramos con ack manual
> y `prefetch=1`, así que se rehace un solo fragmento. Si un fragmento tira workers una y otra vez,
> la cola quorum tiene un límite de 2 reentregas y después lo manda a la DLQ. Ahí el dlq-monitor lo
> reintenta y, si sigue fallando, lo estaciona para que el admin lo reprocese."

**Al terminar**, el script deja 2 workers. Volver a 3:
```bash
docker compose -f docker-compose.yml -f docker-compose.r4.yml up -d --no-deps --scale worker=3 worker
```

---

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Cómo detectan que un worker murió? | Por la conexión AMQP: ante un crash se cierra el socket y es inmediato. Si el worker queda colgado, el heartbeat de 60 s corta la conexión. El heartbeat en Redis es solo para observar y alertar. |
| ¿Y si el resultado llega duplicado? | El joiner es idempotente: anota cada fragmento en un *set* de Redis, así que procesar dos veces no rompe nada. |
| ¿Por qué no mandan la imagen por RabbitMQ? | Por la cola viajan referencias chicas; los bytes van por Redis. Si no, 100 MB serían un mensaje de 100 MB en el broker. |
| ¿Qué tipo de cola usan? | La de tareas es **quorum**, durable, con límite de entregas y DLX. Las demás son classic y durables. Todos los mensajes se publican persistentes (`delivery_mode=2`). Ver [rabbit.py](../services/common/tp3common/rabbit.py). |
| ¿Se guarda en disco? | En GKE sí: RabbitMQ y Redis tienen un disco persistente de 8 GB y Redis usa `appendonly`. En compose las colas se escriben en disco dentro del contenedor, sin volumen: sobreviven a un `restart` pero no a un `down`. Los logs van a memoria y a `/var/log/tp3/<servicio>.log`, que es lo que pide la consigna. |
| ¿Corre en Kubernetes? | Sí: cada `exN/k8s.yaml` tiene el productor como Job y los consumidores como Deployment, y la app tiene sus manifiestos en `TP3/k8s`. En la demo usamos Docker porque es más rápido. |

**Si algo falla en vivo:** cada README tiene la salida esperada pegada. Mostrá la del ejemplo que
falló y seguí.
