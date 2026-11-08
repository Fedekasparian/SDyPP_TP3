# R5: imágenes en Redis vs imágenes en bucket GCS

Comparación celda por celda de la matriz R5 (108 celdas: V1 = tamaño de imagen, V3 = VMs workers, VA = usuarios concurrentes, VB = operaciones encadenadas, VC = jobs por usuario; meseta 20 s) entre la versión vieja, donde los bytes de las imágenes vivían en Redis (corrida del 07/11/2026, loadtest/results-gke), y la versión nueva, donde las imágenes van a un bucket GCS y Redis guarda solo punteros gs:// (corrida del 08/11/2026, run 42514042043, workers en VMs normales).

Cómo leer las tablas: jobs = jobs terminados en la celda; p50/p95 = latencia de punta a punta del job en segundos ("-" = no terminó ningún job, no hay latencia para medir); Δ% = cambio del bucket respecto de Redis (en latencia, negativo es mejor). SLO: VA=1 p95 ≤ 10 s, VA>1 p95 ≤ 45 s, error < 1 %.

## 1. Resumen

| V1 | V3 | celdas | jobs terminados Redis | jobs terminados GCS | Δ% | celdas sin ningún job Redis | celdas sin ningún job GCS | SLO Redis | SLO GCS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10KB | 2 | 27 | 4683 | 967 | -79% | 0 | 11 | 23/27 | 8/27 |
| 10KB | 6 | 27 | 7290 | 0 | -100% | 0 | 27 | 27/27 | 0/27 |
| 1MB | 2 | 27 | 2019 | 0 | -100% | 1 | 27 | 19/27 | 0/27 |
| 1MB | 6 | 27 | 2113 | 0 | -100% | 1 | 27 | 18/27 | 0/27 |

Celdas que cumplen el SLO en total: Redis 87/108, bucket GCS 8/108.

## 2. Cuellos de botella detectados

| Cuello de botella | celdas Redis | celdas GCS |
| --- | --- | --- |
| workers | 40 | 56 |
| split | 0 | 44 |
| ninguno | 33 | 7 |
| nodo GKE | 33 | 0 |
| joiner | 2 | 0 |
| sin captura de Prometheus | 0 | 1 |

## 3. Detalle celda por celda

### V1 = 10KB, V3 = 2 workers

| VA | VB | VC | jobs R | jobs G | Δ% | p50 R | p50 G | Δ% | p95 R | p95 G | Δ% | SLO R/G | cuello Redis | cuello GCS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 40 | 20 | -50% | 0.626 | 1.198 | +91% | 0.633 | 1.279 | +102% | si / si | ninguno | ninguno |
| 1 | 1 | 10 | 355 | 110 | -69% | 0.691 | 2.265 | +228% | 1.211 | 3.39 | +180% | si / si | ninguno | ninguno |
| 1 | 1 | 50 | 901 | 156 | -83% | 1.419 | 11.493 | +710% | 1.892 | 12.477 | +559% | si / no | workers | workers |
| 1 | 2 | 1 | 41 | 20 | -51% | 0.616 | 1.193 | +94% | 0.647 | 1.743 | +169% | si / si | ninguno | ninguno |
| 1 | 2 | 10 | 363 | 113 | -69% | 0.695 | 2.267 | +226% | 0.723 | 2.813 | +289% | si / si | ninguno | ninguno |
| 1 | 2 | 50 | 824 | 158 | -81% | 1.717 | 11.371 | +562% | 2.282 | 12.076 | +429% | si / no | workers | workers |
| 1 | 3 | 1 | 41 | 22 | -46% | 0.61 | 1.183 | +94% | 0.658 | 1.2 | +82% | si / si | ninguno | ninguno |
| 1 | 3 | 10 | 350 | 113 | -68% | 0.694 | 2.268 | +227% | 1.287 | 2.806 | +118% | si / si | ninguno | ninguno |
| 1 | 3 | 50 | 903 | 157 | -83% | 1.34 | 11.406 | +751% | 1.957 | 12.01 | +514% | si / no | workers | workers |
| 10 | 1 | 1 | 33 | 3 | -91% | 0.656 | 8.877 | +1253% | 1.3 | 9.354 | +620% | si / si | ninguno | ninguno |
| 10 | 1 | 10 | 53 | 17 | -68% | 4.897 | 24.795 | +406% | 7.234 | 26.672 | +269% | si / si | workers | sin captura de Prometheus |
| 10 | 1 | 50 | 132 | 20 | -85% | 15.036 | 31.988 | +113% | 16.418 | 56.075 | +242% | si / no | workers | workers |
| 10 | 2 | 1 | 20 | 0 | -100% | 1.3 | - | - | 1.353 | - | - | si / no | ninguno | workers |
| 10 | 2 | 10 | 90 | 8 | -91% | 3.021 | 49.398 | +1535% | 3.731 | 55.221 | +1380% | si / no | workers | workers |
| 10 | 2 | 50 | 130 | 21 | -84% | 16.326 | 31.972 | +96% | 30.72 | 54.692 | +78% | si / no | workers | workers |
| 10 | 3 | 1 | 41 | 0 | -100% | 0.614 | - | - | 0.634 | - | - | si / no | workers | workers |
| 10 | 3 | 10 | 94 | 8 | -91% | 2.976 | 48.459 | +1528% | 3.528 | 55.264 | +1466% | si / no | workers | workers |
| 10 | 3 | 50 | 88 | 21 | -76% | 22.528 | 34.628 | +54% | 29.747 | 55.507 | +87% | si / no | workers | workers |
| 50 | 1 | 1 | 11 | 0 | -100% | 2.464 | - | - | 2.49 | - | - | si / no | ninguno | workers |
| 50 | 1 | 10 | 21 | 0 | -100% | 21.058 | - | - | 32.816 | - | - | si / no | workers | workers |
| 50 | 1 | 50 | 31 | 0 | -100% | 28.525 | - | - | 51.157 | - | - | no / no | workers | workers |
| 50 | 2 | 1 | 10 | 0 | -100% | 2.549 | - | - | 2.563 | - | - | si / no | workers | workers |
| 50 | 2 | 10 | 17 | 0 | -100% | 22.753 | - | - | 30.902 | - | - | si / no | workers | workers |
| 50 | 2 | 50 | 33 | 0 | -100% | 28.473 | - | - | 52.577 | - | - | no / no | workers | workers |
| 50 | 3 | 1 | 1 | 0 | -100% | 47.154 | - | - | 47.154 | - | - | no / no | workers | workers |
| 50 | 3 | 10 | 26 | 0 | -100% | 16.248 | - | - | 17.178 | - | - | si / no | workers | workers |
| 50 | 3 | 50 | 34 | 0 | -100% | 29.655 | - | - | 53.169 | - | - | no / no | workers | workers |

### V1 = 10KB, V3 = 6 workers

| VA | VB | VC | jobs R | jobs G | Δ% | p50 R | p50 G | Δ% | p95 R | p95 G | Δ% | SLO R/G | cuello Redis | cuello GCS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 40 | 0 | -100% | 0.582 | - | - | 0.642 | - | - | si / no | ninguno | workers |
| 1 | 1 | 10 | 432 | 0 | -100% | 0.581 | - | - | 0.598 | - | - | si / no | ninguno | workers |
| 1 | 1 | 50 | 1336 | 0 | -100% | 0.799 | - | - | 1.428 | - | - | si / no | ninguno | workers |
| 1 | 2 | 1 | 44 | 0 | -100% | 0.578 | - | - | 0.585 | - | - | si / no | ninguno | workers |
| 1 | 2 | 10 | 434 | 0 | -100% | 0.579 | - | - | 0.602 | - | - | si / no | ninguno | workers |
| 1 | 2 | 50 | 1300 | 0 | -100% | 0.882 | - | - | 1.46 | - | - | si / no | joiner | workers |
| 1 | 3 | 1 | 43 | 0 | -100% | 0.58 | - | - | 0.584 | - | - | si / no | nodo GKE | workers |
| 1 | 3 | 10 | 433 | 0 | -100% | 0.579 | - | - | 0.598 | - | - | si / no | ninguno | workers |
| 1 | 3 | 50 | 1280 | 0 | -100% | 0.833 | - | - | 1.585 | - | - | si / no | joiner | workers |
| 10 | 1 | 1 | 43 | 0 | -100% | 0.58 | - | - | 0.591 | - | - | si / no | ninguno | workers |
| 10 | 1 | 10 | 223 | 0 | -100% | 1.157 | - | - | 1.709 | - | - | si / no | workers | split |
| 10 | 1 | 50 | 231 | 0 | -100% | 6.412 | - | - | 8.007 | - | - | si / no | workers | split |
| 10 | 2 | 1 | 43 | 0 | -100% | 0.582 | - | - | 0.599 | - | - | si / no | ninguno | split |
| 10 | 2 | 10 | 211 | 0 | -100% | 1.162 | - | - | 1.78 | - | - | si / no | workers | split |
| 10 | 2 | 50 | 230 | 0 | -100% | 6.793 | - | - | 7.51 | - | - | si / no | workers | split |
| 10 | 3 | 1 | 43 | 0 | -100% | 0.583 | - | - | 0.595 | - | - | si / no | ninguno | split |
| 10 | 3 | 10 | 226 | 0 | -100% | 1.157 | - | - | 1.263 | - | - | si / no | workers | split |
| 10 | 3 | 50 | 233 | 0 | -100% | 6.706 | - | - | 7.81 | - | - | si / no | workers | split |
| 50 | 1 | 1 | 22 | 0 | -100% | 1.139 | - | - | 1.16 | - | - | si / no | nodo GKE | split |
| 50 | 1 | 10 | 53 | 0 | -100% | 6.029 | - | - | 6.637 | - | - | si / no | workers | split |
| 50 | 1 | 50 | 81 | 0 | -100% | 26.415 | - | - | 33.737 | - | - | si / no | workers | split |
| 50 | 2 | 1 | 22 | 0 | -100% | 1.138 | - | - | 1.152 | - | - | si / no | nodo GKE | split |
| 50 | 2 | 10 | 54 | 0 | -100% | 5.554 | - | - | 6.129 | - | - | si / no | workers | split |
| 50 | 2 | 50 | 79 | 0 | -100% | 28.365 | - | - | 37.806 | - | - | si / no | workers | split |
| 50 | 3 | 1 | 22 | 0 | -100% | 1.138 | - | - | 1.148 | - | - | si / no | nodo GKE | split |
| 50 | 3 | 10 | 52 | 0 | -100% | 5.72 | - | - | 6.656 | - | - | si / no | workers | split |
| 50 | 3 | 50 | 80 | 0 | -100% | 26.485 | - | - | 34.988 | - | - | si / no | workers | split |

### V1 = 1MB, V3 = 2 workers

| VA | VB | VC | jobs R | jobs G | Δ% | p50 R | p50 G | Δ% | p95 R | p95 G | Δ% | SLO R/G | cuello Redis | cuello GCS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 1 | 0 | -100% | 43.927 | - | - | 43.927 | - | - | no / no | workers | workers |
| 1 | 1 | 10 | 226 | 0 | -100% | 1.009 | - | - | 1.635 | - | - | si / no | ninguno | workers |
| 1 | 1 | 50 | 243 | 0 | -100% | 5.888 | - | - | 7.764 | - | - | si / no | ninguno | workers |
| 1 | 2 | 1 | 36 | 0 | -100% | 0.674 | - | - | 0.901 | - | - | si / no | nodo GKE | workers |
| 1 | 2 | 10 | 266 | 0 | -100% | 0.773 | - | - | 1.537 | - | - | si / no | ninguno | workers |
| 1 | 2 | 50 | 283 | 0 | -100% | 5.412 | - | - | 6.162 | - | - | si / no | nodo GKE | workers |
| 1 | 3 | 1 | 40 | 0 | -100% | 0.626 | - | - | 0.705 | - | - | si / no | nodo GKE | workers |
| 1 | 3 | 10 | 285 | 0 | -100% | 0.734 | - | - | 1.354 | - | - | si / no | ninguno | workers |
| 1 | 3 | 50 | 285 | 0 | -100% | 5.336 | - | - | 6.111 | - | - | si / no | nodo GKE | workers |
| 10 | 1 | 1 | 11 | 0 | -100% | 2.465 | - | - | 2.498 | - | - | si / no | nodo GKE | workers |
| 10 | 1 | 10 | 34 | 0 | -100% | 8.779 | - | - | 11.024 | - | - | si / no | ninguno | workers |
| 10 | 1 | 50 | 46 | 0 | -100% | 34.559 | - | - | 51.739 | - | - | no / no | nodo GKE | workers |
| 10 | 2 | 1 | 10 | 0 | -100% | 1.921 | - | - | 5.743 | - | - | si / no | nodo GKE | workers |
| 10 | 2 | 10 | 40 | 0 | -100% | 7.674 | - | - | 8.41 | - | - | si / no | nodo GKE | workers |
| 10 | 2 | 50 | 56 | 0 | -100% | 30.72 | - | - | 46.611 | - | - | no / no | nodo GKE | workers |
| 10 | 3 | 1 | 13 | 0 | -100% | 1.931 | - | - | 2.011 | - | - | si / no | nodo GKE | workers |
| 10 | 3 | 10 | 40 | 0 | -100% | 7.721 | - | - | 8.745 | - | - | si / no | ninguno | workers |
| 10 | 3 | 50 | 63 | 0 | -100% | 30.059 | - | - | 51.915 | - | - | no / no | nodo GKE | workers |
| 50 | 1 | 1 | 3 | 0 | -100% | 9.966 | - | - | 10.752 | - | - | si / no | nodo GKE | workers |
| 50 | 1 | 10 | 8 | 0 | -100% | 33.429 | - | - | 39.678 | - | - | no / no | workers | workers |
| 50 | 1 | 50 | 0 | 0 | - | - | - | - | - | - | - | no / no | ninguno | workers |
| 50 | 2 | 1 | 1 | 0 | -100% | 34.106 | - | - | 34.106 | - | - | si / no | workers | workers |
| 50 | 2 | 10 | 12 | 0 | -100% | 29.666 | - | - | 41.524 | - | - | si / no | workers | workers |
| 50 | 2 | 50 | 2 | 0 | -100% | 39.437 | - | - | 43.501 | - | - | no / no | nodo GKE | workers |
| 50 | 3 | 1 | 1 | 0 | -100% | 28.766 | - | - | 28.766 | - | - | si / no | nodo GKE | workers |
| 50 | 3 | 10 | 13 | 0 | -100% | 32.028 | - | - | 37.113 | - | - | si / no | workers | workers |
| 50 | 3 | 50 | 1 | 0 | -100% | 17.313 | - | - | 17.313 | - | - | no / no | workers | workers |

### V1 = 1MB, V3 = 6 workers

| VA | VB | VC | jobs R | jobs G | Δ% | p50 R | p50 G | Δ% | p95 R | p95 G | Δ% | SLO R/G | cuello Redis | cuello GCS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 42 | 0 | -100% | 0.604 | - | - | 0.619 | - | - | si / no | nodo GKE | split |
| 1 | 1 | 10 | 241 | 0 | -100% | 1.207 | - | - | 1.405 | - | - | si / no | ninguno | split |
| 1 | 1 | 50 | 238 | 0 | -100% | 6.103 | - | - | 8.416 | - | - | si / no | nodo GKE | split |
| 1 | 2 | 1 | 42 | 0 | -100% | 0.597 | - | - | 0.604 | - | - | si / no | nodo GKE | split |
| 1 | 2 | 10 | 297 | 0 | -100% | 0.729 | - | - | 1.327 | - | - | si / no | ninguno | split |
| 1 | 2 | 50 | 280 | 0 | -100% | 5.314 | - | - | 6.667 | - | - | si / no | nodo GKE | split |
| 1 | 3 | 1 | 42 | 0 | -100% | 0.595 | - | - | 0.609 | - | - | si / no | ninguno | split |
| 1 | 3 | 10 | 295 | 0 | -100% | 0.722 | - | - | 1.333 | - | - | si / no | ninguno | split |
| 1 | 3 | 50 | 272 | 0 | -100% | 5.324 | - | - | 6.793 | - | - | si / no | nodo GKE | split |
| 10 | 1 | 1 | 14 | 0 | -100% | 1.871 | - | - | 1.922 | - | - | si / no | ninguno | split |
| 10 | 1 | 10 | 36 | 0 | -100% | 8.78 | - | - | 10.344 | - | - | si / no | ninguno | split |
| 10 | 1 | 50 | 48 | 0 | -100% | 32.496 | - | - | 53.524 | - | - | no / no | nodo GKE | split |
| 10 | 2 | 1 | 13 | 0 | -100% | 1.354 | - | - | 4.264 | - | - | si / no | nodo GKE | split |
| 10 | 2 | 10 | 38 | 0 | -100% | 7.317 | - | - | 9.456 | - | - | si / no | ninguno | split |
| 10 | 2 | 50 | 55 | 0 | -100% | 30.657 | - | - | 43.206 | - | - | no / no | nodo GKE | split |
| 10 | 3 | 1 | 16 | 0 | -100% | 1.452 | - | - | 1.996 | - | - | si / no | nodo GKE | split |
| 10 | 3 | 10 | 40 | 0 | -100% | 7.261 | - | - | 8.598 | - | - | si / no | ninguno | split |
| 10 | 3 | 50 | 61 | 0 | -100% | 32.102 | - | - | 46.785 | - | - | no / no | nodo GKE | split |
| 50 | 1 | 1 | 3 | 0 | -100% | 8.175 | - | - | 8.209 | - | - | si / no | nodo GKE | split |
| 50 | 1 | 10 | 10 | 0 | -100% | 35.178 | - | - | 49.225 | - | - | no / no | nodo GKE | split |
| 50 | 1 | 50 | 2 | 0 | -100% | 23.614 | - | - | 32.523 | - | - | no / no | nodo GKE | split |
| 50 | 2 | 1 | 0 | 0 | - | - | - | - | - | - | - | no / no | nodo GKE | split |
| 50 | 2 | 10 | 10 | 0 | -100% | 32.641 | - | - | 38.254 | - | - | no / no | workers | split |
| 50 | 2 | 50 | 2 | 0 | -100% | 39.703 | - | - | 42.359 | - | - | no / no | workers | split |
| 50 | 3 | 1 | 1 | 0 | -100% | 27.902 | - | - | 27.902 | - | - | si / no | nodo GKE | split |
| 50 | 3 | 10 | 13 | 0 | -100% | 29.476 | - | - | 41.203 | - | - | si / no | workers | split |
| 50 | 3 | 50 | 2 | 0 | -100% | 33.461 | - | - | 34.687 | - | - | no / no | workers | split |

R = Redis, G = bucket GCS. Tiempos en segundos.

## 4. Conclusiones

Con las imágenes en GCS el sistema terminó muchos menos jobs: 967 en toda la matriz contra 16.105 con Redis. Cumplen el SLO 8 de 108 celdas con GCS contra 87 de 108 con Redis.

Incluso con poca carga, donde la comparación es justa porque no hay nada encolado, la versión con GCS es más lenta: con 1 usuario y 10KB el p95 pasa de 0,63 s a 1,28 s (1 job por usuario) y de 1,89 s a 12,48 s (50 jobs por usuario), y se terminan entre 2 y 6 veces menos jobs.

Los workers casi no usan CPU (unos 0,06 núcleos por VM) mientras la cola de tareas crece: no les falta CPU, están esperando las lecturas y escrituras contra el bucket. Cada fragmento ahora implica bajar un objeto de GCS, procesarlo y subir otro, y lo mismo pasa en split y en joiner, que también acumulan cola.

Desde la celda 10KB, V3=2, VA=10, VB=2 el sistema ya no da abasto: la cola de tareas crece hasta unas 15.000 y desde ahí no termina ningún job dentro de los 60 s. La matriz no espera a que se vacíen las colas entre celdas, así que todas las celdas siguientes, incluida toda la parte de V3=6, arrancan con ese atraso. En 92 de las 108 celdas no terminó ningún job; esas celdas miden el atraso acumulado y no la celda en sí, así que con esta corrida no se puede saber si pasar de 2 a 6 workers mejora con GCS.

Lo que sí resolvió el cambio: Redis no se reinició ni una vez en toda la corrida (antes terminaba OOMKilled con las imágenes adentro) y no hubo errores ni mensajes en la DLQ.

En resumen: sacar las imágenes de Redis arregló el problema de memoria, pero tal como está implementado el acceso al bucket es mucho más lento y pasó a ser el cuello de botella de todo el pipeline.
