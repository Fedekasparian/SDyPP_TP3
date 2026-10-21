# Hit #0: patrones de mensajería con RabbitMQ

**Responsable: Integrante A**

Cada ejemplo es un programa independiente con su código, sus manifiestos de Kubernetes y su README.

| Ej. | Patrón | Estado |
|---|---|---|
| [ex1](ex1/) | Message Queue punto a punto (round-robin) | Listo |
| [ex2](ex2/) | Pub/Sub con exchange `fanout` | Listo |
| [ex3](ex3/) | Dead Letter Queue | Listo |
| [ex4](ex4/) | Retry con backoff exponencial y DLQ | Listo |
| [ex5](ex5/) | Discusión comparativa (solo documentación) | Listo |

## Cómo correr

**Opción 1, solo Docker (la más rápida):** levanta un RabbitMQ aislado, corre el escenario y reproduce las salidas que figuran en cada README.
```bash
bash TP3/queue/run_demo.sh all        # o ex1 | ex2 | ex3 | ex4
```

**Opción 2, Python local** contra el RabbitMQ de compose (UI en http://localhost:15672 con el usuario y la contraseña del .env):
```bash
docker compose up -d rabbitmq
pip install pika==1.3.2
export RABBIT_URL="amqp://tp3:<pass>@localhost:5672/" PYTHONPATH=TP3/queue
python TP3/queue/ex1/consumer.py &  python TP3/queue/ex1/producer.py
```

**Opción 3, Kubernetes:** todos los ejemplos usan una sola imagen, [`Dockerfile`](Dockerfile). Cada `exN/k8s.yaml` levanta el productor (`Job`) y los consumidores (`Deployment`) en el namespace `tp3`, contra el RabbitMQ de [TP3/k8s/overlays/local/infra-local.yaml](../k8s/overlays/local/infra-local.yaml), con la contraseña del Secret `rabbitmq-auth`.
```bash
docker build -t tp3/queue-examples:dev TP3/queue && minikube image load tp3/queue-examples:dev
kubectl apply -f TP3/queue/ex1/k8s.yaml
```

La conexión ([`common.py`](common.py)) toma `RABBIT_URL`, o la arma con `RABBIT_USER`/`RABBIT_PASS`/`RABBIT_HOST`, y reintenta con backoff de 1/2/4/8 s.

## Relación con la app

Los mismos patrones se usan en [TP3/services](../services/) (ver [rabbit.py](../services/common/tp3common/rabbit.py)):
- **Cola punto a punto**: `tasks.<pool>`, consumida por N workers con `prefetch=1`.
- **Fanout**: `results`, que notifica al joiner y al monitor.
- **DLQ**: `tasks.dlx` → `tasks.dlq` → `dlq-monitor`.
- **Retry**: el dlq-monitor reencola con `attempt+1`. Las conexiones usan backoff de 1/2/4/8 s con tope de 30 s ([retry.py](../services/common/tp3common/retry.py)).
