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
- Capturas del dashboard y de la alerta disparada.

## 7. Requisitos R1 a R5
| Req. | Evidencia | Dónde |
|---|---|---|
| R1 | Captura de `ImagePullBackOff` y del pull exitoso | [r1-evidencia.md](r1-evidencia.md) |
| R2 | Requests inválidos devuelven 400 y la cola no cambia | video, logs |
| R3 | [contrato.md](contrato.md) | |
| R4 | 13 verificaciones locales, tres backends distintos; GKE pendiente | [r4_local.txt](../evidencia/r4_local.txt), [parte B](parte-b.md) |
| R5 | Matriz completa | sección 8 |

## 8. Análisis de desempeño (D)
- Configuración de k6: VUs, ramp-up y duración. Ver [loadtest/README.md](../loadtest/README.md).
- **Hit #3:** tabla V1 × V2 × V3.
- **R5:** matriz VA × VB × VC × V1 × V3 con p50, p95, p99, throughput, tasa de error, SLO y cuello de botella.
- Casos inválidos o fallidos: cuántos terminaron con error claro, cuántos en la DLQ y cuántos se reprocesaron.
- Gráficos.

## 9. Marco conceptual
- NIST SP 800-145: cómo cumple el sistema cada una de las 5 características.
- Cloud native frente a híbrido, cloud-bursting y offloading.
- **CAP** (a investigar): qué eligen RabbitMQ (las colas quorum usan Raft) y Redis (standalone, réplica asincrónica, Sentinel o Cluster) ante una partición de red, y qué implica para nuestra arquitectura (pérdida de fragmentos, jobs que quedan colgados).

## 10. Uso de herramientas de IA
| Integrante | Herramienta | Para qué la usó | Qué hubo que corregir |
|---|---|---|---|
| | Claude Code | Andamiaje inicial del repo, contratos, servicios, IaC y CI | |
| | | | |

## 11. Conclusiones
