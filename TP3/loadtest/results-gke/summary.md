| V1 | V3 | VA | VB | VC | estado | meseta | p50_s | p95_s | p99_s | jobs_ok | throughput_req_s | tasa_error | dlq | timeouts | invalidos_rechazados | slo_ok | cuello_de_botella |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10KB | 2 | 1 | 1 | 1 | medida | 20s | 0.626 | 0.633 | 0.653 | 40 | 3.37 | 0 | 0 | 0 | 2 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.15); domina el recorrido y el polling |
| 10KB | 2 | 1 | 1 | 10 | medida | 20s | 0.691 | 1.211 | 1.299 | 355 | 25.52 | 0 | 0 | 0 | 21 | si | ninguno: sin saturacion (colas max 26, CPU VM 0.02); domina el recorrido y el polling |
| 10KB | 2 | 1 | 1 | 50 | medida | 20s | 1.419 | 1.892 | 2.225 | 901 | 91.87 | 0 | 0 | 0 | 45 | si | workers (VMs) por I/O: cola tasks max 131 con CPU 0.07 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 1 | 2 | 1 | medida | 20s | 0.616 | 0.647 | 0.662 | 41 | 3.42 | 0 | 0 | 0 | 3 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.14); domina el recorrido y el polling |
| 10KB | 2 | 1 | 2 | 10 | medida | 20s | 0.695 | 0.723 | 1.299 | 363 | 25.75 | 0 | 0 | 0 | 20 | si | ninguno: sin saturacion (colas max 16, CPU VM 0.01); domina el recorrido y el polling |
| 10KB | 2 | 1 | 2 | 50 | medida | 20s | 1.717 | 2.282 | 2.358 | 824 | 96.01 | 0 | 0 | 0 | 48 | si | workers (VMs) por I/O: cola tasks max 141 con CPU 0.07 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 1 | 3 | 1 | medida | 20s | 0.61 | 0.658 | 0.774 | 41 | 3.34 | 0 | 0 | 0 | 0 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.14); domina el recorrido y el polling |
| 10KB | 2 | 1 | 3 | 10 | medida | 20s | 0.694 | 1.287 | 1.308 | 350 | 25.23 | 0 | 0 | 0 | 23 | si | ninguno: sin saturacion (colas max 17, CPU VM 0.04); domina el recorrido y el polling |
| 10KB | 2 | 1 | 3 | 50 | medida | 20s | 1.34 | 1.957 | 2.14 | 903 | 93.27 | 0 | 0 | 0 | 62 | si | workers (VMs) por I/O: cola tasks max 130 con CPU 0.08 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 10 | 1 | 1 | medida | 20s | 0.656 | 1.3 | 1.33 | 33 | 3.15 | 0 | 0 | 0 | 4 | si | ninguno: sin saturacion (colas max 31, CPU VM 0.10); domina el recorrido y el polling |
| 10KB | 2 | 10 | 1 | 10 | medida | 20s | 4.897 | 7.234 | 7.326 | 53 | 16.96 | 0 | 0 | 0 | 3 | si | workers (VMs) por I/O: cola tasks max 372 con CPU 0.08 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 10 | 1 | 50 | medida | 20s | 15.036 | 16.418 | 16.863 | 132 | 68.67 | 0 | 0 | 0 | 7 | si | workers (VMs) por I/O: cola tasks max 1916 con CPU 0.09 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 10 | 2 | 1 | medida | 20s | 1.3 | 1.353 | 1.375 | 20 | 2.62 | 0 | 0 | 0 | 1 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.15); domina el recorrido y el polling |
| 10KB | 2 | 10 | 2 | 10 | medida | 20s | 3.021 | 3.731 | 4.041 | 90 | 18.42 | 0 | 0 | 0 | 3 | si | workers (VMs) por I/O: cola tasks max 310 con CPU 0.05 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 10 | 2 | 50 | medida | 20s | 16.326 | 30.72 | 32.196 | 130 | 63.56 | 0 | 0 | 0 | 8 | si | workers (VMs) por I/O: cola tasks max 1943 con CPU 0.14 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 10 | 3 | 1 | medida | 20s | 0.614 | 0.634 | 0.657 | 41 | 3.44 | 0 | 0 | 0 | 3 | si | workers (VMs) por I/O: cola tasks max 252 con CPU 0.09 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 10 | 3 | 10 | medida | 20s | 2.976 | 3.528 | 3.68 | 94 | 18.31 | 0 | 0 | 0 | 6 | si | workers (VMs) por I/O: cola tasks max 364 con CPU 0.10 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 10 | 3 | 50 | medida | 20s | 22.528 | 29.747 | 30.316 | 88 | 64.73 | 0 | 0 | 0 | 4 | si | workers (VMs) por I/O: cola tasks max 1913 con CPU 0.11 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 1 | 1 | medida | 20s | 2.464 | 2.49 | 2.494 | 11 | 2.36 | 0 | 0 | 0 | 0 | si | ninguno: sin saturacion (colas max 12, CPU VM 0.10); domina el recorrido y el polling |
| 10KB | 2 | 50 | 1 | 10 | medida | 20s | 21.058 | 32.816 | 33.333 | 21 | 13.82 | 0 | 0 | 0 | 0 | si | workers (VMs) por I/O: cola tasks max 1911 con CPU 0.09 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 1 | 50 | medida | 20s | 28.525 | 51.157 | 55.49 | 31 | 76.55 | 0 | 0 | 0 | 0 | no | workers (VMs) por I/O: cola tasks max 9865 con CPU 0.10 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 2 | 1 | medida | 20s | 2.549 | 2.563 | 2.567 | 10 | 2.3 | 0 | 0 | 0 | 0 | si | workers (VMs) por I/O: cola tasks max 183 con CPU 0.17 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 2 | 10 | medida | 20s | 22.753 | 30.902 | 31.941 | 17 | 12.69 | 0 | 0 | 0 | 0 | si | workers (VMs) por I/O: cola tasks max 1926 con CPU 0.15 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 2 | 50 | medida | 20s | 28.473 | 52.577 | 54.75 | 33 | 72.47 | 0 | 0 | 0 | 1 | no | workers (VMs) por I/O: cola tasks max 9802 con CPU 0.10 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 3 | 1 | medida | 20s | 47.154 | 47.154 | 47.154 | 1 | 1.99 | 0 | 0 | 0 | 0 | no | workers (VMs) por I/O: cola tasks max 5695 con CPU 0.17 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 3 | 10 | medida | 20s | 16.248 | 17.178 | 17.226 | 26 | 14.36 | 0 | 0 | 0 | 2 | si | workers (VMs) por I/O: cola tasks max 1873 con CPU 0.15 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 2 | 50 | 3 | 50 | medida | 20s | 29.655 | 53.169 | 55.216 | 34 | 72.27 | 0 | 0 | 0 | 4 | no | workers (VMs) por I/O: cola tasks max 9764 con CPU 0.14 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 2 | 1 | 1 | 1 | medida | 20s | 43.927 | 43.927 | 43.927 | 1 | 2.0 | 0 | 0 | 0 | 0 | no | workers (VMs) por I/O: cola tasks max 5785 con CPU 0.16 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 2 | 1 | 1 | 10 | medida | 20s | 1.009 | 1.635 | 2.11 | 226 | 19.89 | 0 | 0 | 0 | 15 | si | ninguno: sin saturacion (colas max 1, CPU VM 0.15); domina el recorrido y el polling |
| 1MB | 2 | 1 | 1 | 50 | medida | 20s | 5.888 | 7.764 | 7.926 | 243 | 67.82 | 0 | 0 | 0 | 14 | si | ninguno: sin saturacion (colas max 33, CPU VM 0.29); domina el recorrido y el polling |
| 1MB | 2 | 1 | 2 | 1 | medida | 20s | 0.674 | 0.901 | 0.92 | 36 | 3.03 | 0 | 0 | 0 | 0 | si | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 2 | 1 | 2 | 10 | medida | 20s | 0.773 | 1.537 | 2.154 | 266 | 21.78 | 0 | 0 | 0 | 13 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.27); domina el recorrido y el polling |
| 1MB | 2 | 1 | 2 | 50 | medida | 20s | 5.412 | 6.162 | 6.35 | 283 | 75.07 | 0 | 0 | 0 | 10 | si | nodo GKE 10.128.15.218:9100 al 99% de CPU |
| 1MB | 2 | 1 | 3 | 1 | medida | 20s | 0.626 | 0.705 | 0.73 | 40 | 3.36 | 0 | 0 | 0 | 2 | si | nodo GKE 10.128.15.218:9100 al 99% de CPU |
| 1MB | 2 | 1 | 3 | 10 | medida | 20s | 0.734 | 1.354 | 1.473 | 285 | 23.18 | 0 | 0 | 0 | 16 | si | ninguno: sin saturacion (colas max 3, CPU VM 0.14); domina el recorrido y el polling |
| 1MB | 2 | 1 | 3 | 50 | medida | 20s | 5.336 | 6.111 | 6.361 | 285 | 76.48 | 0 | 0 | 0 | 15 | si | nodo GKE 10.128.15.218:9100 al 87% de CPU |
| 1MB | 2 | 10 | 1 | 1 | medida | 20s | 2.465 | 2.498 | 2.503 | 11 | 2.37 | 0 | 0 | 0 | 1 | si | nodo GKE 10.128.15.218:9100 al 87% de CPU |
| 1MB | 2 | 10 | 1 | 10 | medida | 20s | 8.779 | 11.024 | 11.138 | 34 | 15.39 | 0 | 0 | 0 | 0 | si | ninguno: sin saturacion (colas max 25, CPU VM 0.17); domina el recorrido y el polling |
| 1MB | 2 | 10 | 1 | 50 | medida | 20s | 34.559 | 51.739 | 54.243 | 46 | 53.65 | 0 | 0 | 0 | 3 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 2 | 10 | 2 | 1 | medida | 20s | 1.921 | 5.743 | 8.217 | 10 | 2.34 | 0 | 0 | 0 | 0 | si | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 2 | 10 | 2 | 10 | medida | 20s | 7.674 | 8.41 | 8.547 | 40 | 15.34 | 0 | 0 | 0 | 1 | si | nodo GKE 10.128.15.218:9100 al 92% de CPU |
| 1MB | 2 | 10 | 2 | 50 | medida | 20s | 30.72 | 46.611 | 49.602 | 56 | 50.13 | 0.0345 | 0 | 0 | 3 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 2 | 10 | 3 | 1 | medida | 20s | 1.931 | 2.011 | 2.014 | 13 | 2.42 | 0 | 0 | 0 | 1 | si | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 2 | 10 | 3 | 10 | medida | 20s | 7.721 | 8.745 | 8.871 | 40 | 15.27 | 0 | 0 | 0 | 1 | si | ninguno: sin saturacion (colas max 31, CPU VM 0.22); domina el recorrido y el polling |
| 1MB | 2 | 10 | 3 | 50 | medida | 20s | 30.059 | 51.915 | 55.078 | 63 | 45.35 | 0 | 0 | 0 | 6 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 2 | 50 | 1 | 1 | medida | 20s | 9.966 | 10.752 | 10.822 | 3 | 2.01 | 0 | 0 | 0 | 0 | si | nodo GKE 10.128.15.218:9100 al 85% de CPU |
| 1MB | 2 | 50 | 1 | 10 | medida | 20s | 33.429 | 39.678 | 40.406 | 8 | 12.72 | 0.1111 | 0 | 0 | 0 | no | workers (VMs) por I/O: cola tasks max 341 con CPU 0.24 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 2 | 50 | 1 | 50 | medida | 20s | nan | nan | nan | 0 | 6.83 | 1 | 0 | 0 | 4 | no | ninguno: sin saturacion (colas max 11, CPU VM 0.27); domina el recorrido y el polling |
| 1MB | 2 | 50 | 2 | 1 | medida | 20s | 34.106 | 34.106 | 34.106 | 1 | 1.88 | 0 | 0 | 0 | 0 | si | workers (VMs) por I/O: cola tasks max 255 con CPU 0.12 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 2 | 50 | 2 | 10 | medida | 20s | 29.666 | 41.524 | 43.9 | 12 | 10.58 | 0 | 0 | 0 | 1 | si | workers (VMs) por I/O: cola tasks max 143 con CPU 0.21 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 2 | 50 | 2 | 50 | medida | 20s | 39.437 | 43.501 | 43.863 | 2 | 7.95 | 0.75 | 0 | 0 | 1 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 2 | 50 | 3 | 1 | medida | 20s | 28.766 | 28.766 | 28.766 | 1 | 2.06 | 0 | 0 | 0 | 0 | si | nodo GKE 10.128.15.218:9100 al 99% de CPU |
| 1MB | 2 | 50 | 3 | 10 | medida | 20s | 32.028 | 37.113 | 37.43 | 13 | 10.44 | 0 | 0 | 0 | 2 | si | workers (VMs) por I/O: cola tasks max 202 con CPU 0.16 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 2 | 50 | 3 | 50 | medida | 20s | 17.313 | 17.313 | 17.313 | 1 | 12.32 | 0.875 | 0 | 0 | 2 | no | workers (VMs) por I/O: cola tasks max 283 con CPU 0.22 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 1 | 1 | 1 | medida | 20s | 0.582 | 0.642 | 1.602 | 40 | 3.35 | 0 | 0 | 0 | 1 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.00); domina el recorrido y el polling |
| 10KB | 6 | 1 | 1 | 10 | medida | 20s | 0.581 | 0.598 | 0.609 | 432 | 30.41 | 0 | 0 | 0 | 35 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.01); domina el recorrido y el polling |
| 10KB | 6 | 1 | 1 | 50 | medida | 20s | 0.799 | 1.428 | 1.735 | 1336 | 101.83 | 0 | 0 | 0 | 76 | si | ninguno: sin saturacion (colas max 40, CPU VM 0.05); domina el recorrido y el polling |
| 10KB | 6 | 1 | 2 | 1 | medida | 20s | 0.578 | 0.585 | 0.594 | 44 | 3.63 | 0 | 0 | 0 | 2 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.13); domina el recorrido y el polling |
| 10KB | 6 | 1 | 2 | 10 | medida | 20s | 0.579 | 0.602 | 0.626 | 434 | 29.77 | 0 | 0 | 0 | 20 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.03); domina el recorrido y el polling |
| 10KB | 6 | 1 | 2 | 50 | medida | 20s | 0.882 | 1.46 | 1.722 | 1300 | 102.39 | 0 | 0 | 0 | 53 | si | joiner: cola results.joiner max 86, CPU joiner 7% |
| 10KB | 6 | 1 | 3 | 1 | medida | 20s | 0.58 | 0.584 | 0.591 | 43 | 3.63 | 0 | 0 | 0 | 2 | si | nodo GKE 10.128.15.218:9100 al 94% de CPU |
| 10KB | 6 | 1 | 3 | 10 | medida | 20s | 0.579 | 0.598 | 0.612 | 433 | 30.09 | 0 | 0 | 0 | 19 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.03); domina el recorrido y el polling |
| 10KB | 6 | 1 | 3 | 50 | medida | 20s | 0.833 | 1.585 | 1.917 | 1280 | 98.93 | 0 | 0 | 0 | 60 | si | joiner: cola results.joiner max 96, CPU joiner 10% |
| 10KB | 6 | 10 | 1 | 1 | medida | 20s | 0.58 | 0.591 | 0.602 | 43 | 3.68 | 0 | 0 | 0 | 4 | si | ninguno: sin saturacion (colas max 4, CPU VM 0.08); domina el recorrido y el polling |
| 10KB | 6 | 10 | 1 | 10 | medida | 20s | 1.157 | 1.709 | 1.778 | 223 | 22.63 | 0 | 0 | 0 | 16 | si | workers (VMs) por I/O: cola tasks max 155 con CPU 0.09 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 10 | 1 | 50 | medida | 20s | 6.412 | 8.007 | 8.099 | 231 | 78.12 | 0 | 0 | 0 | 9 | si | workers (VMs) por I/O: cola tasks max 1211 con CPU 0.15 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 10 | 2 | 1 | medida | 20s | 0.582 | 0.599 | 0.609 | 43 | 3.63 | 0 | 0 | 0 | 3 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.15); domina el recorrido y el polling |
| 10KB | 6 | 10 | 2 | 10 | medida | 20s | 1.162 | 1.78 | 1.969 | 211 | 22.49 | 0 | 0 | 0 | 12 | si | workers (VMs) por I/O: cola tasks max 108 con CPU 0.10 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 10 | 2 | 50 | medida | 20s | 6.793 | 7.51 | 7.847 | 230 | 79.74 | 0 | 0 | 0 | 16 | si | workers (VMs) por I/O: cola tasks max 1060 con CPU 0.15 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 10 | 3 | 1 | medida | 20s | 0.583 | 0.595 | 0.603 | 43 | 3.55 | 0 | 0 | 0 | 0 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.22); domina el recorrido y el polling |
| 10KB | 6 | 10 | 3 | 10 | medida | 20s | 1.157 | 1.263 | 1.731 | 226 | 22.91 | 0 | 0 | 0 | 13 | si | workers (VMs) por I/O: cola tasks max 141 con CPU 0.07 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 10 | 3 | 50 | medida | 20s | 6.706 | 7.81 | 8.104 | 233 | 79.29 | 0 | 0 | 0 | 18 | si | workers (VMs) por I/O: cola tasks max 1331 con CPU 0.20 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 50 | 1 | 1 | medida | 20s | 1.139 | 1.16 | 1.619 | 22 | 2.89 | 0 | 0 | 0 | 1 | si | nodo GKE 10.128.15.218:9100 al 94% de CPU |
| 10KB | 6 | 50 | 1 | 10 | medida | 20s | 6.029 | 6.637 | 6.653 | 53 | 17.3 | 0 | 0 | 0 | 7 | si | workers (VMs) por I/O: cola tasks max 1626 con CPU 0.12 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 50 | 1 | 50 | medida | 20s | 26.415 | 33.737 | 34.26 | 81 | 65.54 | 0 | 0 | 0 | 4 | si | workers (VMs) por I/O: cola tasks max 6692 con CPU 0.17 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 50 | 2 | 1 | medida | 20s | 1.138 | 1.152 | 1.161 | 22 | 2.92 | 0 | 0 | 0 | 1 | si | nodo GKE 10.128.15.218:9100 al 87% de CPU |
| 10KB | 6 | 50 | 2 | 10 | medida | 20s | 5.554 | 6.129 | 6.417 | 54 | 17.46 | 0 | 0 | 0 | 2 | si | workers (VMs) por I/O: cola tasks max 1383 con CPU 0.14 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 50 | 2 | 50 | medida | 20s | 28.365 | 37.806 | 38.635 | 79 | 64.11 | 0 | 0 | 0 | 6 | si | workers (VMs) por I/O: cola tasks max 6337 con CPU 0.22 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 50 | 3 | 1 | medida | 20s | 1.138 | 1.148 | 1.154 | 22 | 2.94 | 0 | 0 | 0 | 2 | si | nodo GKE 10.128.15.218:9100 al 89% de CPU |
| 10KB | 6 | 50 | 3 | 10 | medida | 20s | 5.72 | 6.656 | 6.966 | 52 | 17.16 | 0 | 0 | 0 | 0 | si | workers (VMs) por I/O: cola tasks max 1584 con CPU 0.13 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 10KB | 6 | 50 | 3 | 50 | medida | 20s | 26.485 | 34.988 | 35.446 | 80 | 65.48 | 0 | 0 | 0 | 1 | si | workers (VMs) por I/O: cola tasks max 7714 con CPU 0.18 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 6 | 1 | 1 | 1 | medida | 20s | 0.604 | 0.619 | 0.632 | 42 | 3.54 | 0 | 0 | 0 | 3 | si | nodo GKE 10.128.15.218:9100 al 89% de CPU |
| 1MB | 6 | 1 | 1 | 10 | medida | 20s | 1.207 | 1.405 | 1.947 | 241 | 22.27 | 0 | 0 | 0 | 14 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.08); domina el recorrido y el polling |
| 1MB | 6 | 1 | 1 | 50 | medida | 20s | 6.103 | 8.416 | 8.805 | 238 | 74.94 | 0 | 0 | 0 | 7 | si | nodo GKE 10.128.15.218:9100 al 86% de CPU |
| 1MB | 6 | 1 | 2 | 1 | medida | 20s | 0.597 | 0.604 | 0.609 | 42 | 3.52 | 0 | 0 | 0 | 1 | si | nodo GKE 10.128.15.218:9100 al 86% de CPU |
| 1MB | 6 | 1 | 2 | 10 | medida | 20s | 0.729 | 1.327 | 1.392 | 297 | 23.12 | 0 | 0 | 0 | 14 | si | ninguno: sin saturacion (colas max 2, CPU VM 0.06); domina el recorrido y el polling |
| 1MB | 6 | 1 | 2 | 50 | medida | 20s | 5.314 | 6.667 | 6.921 | 280 | 77.37 | 0 | 0 | 0 | 18 | si | nodo GKE 10.128.15.218:9100 al 88% de CPU |
| 1MB | 6 | 1 | 3 | 1 | medida | 20s | 0.595 | 0.609 | 0.616 | 42 | 3.49 | 0 | 0 | 0 | 0 | si | ninguno: sin saturacion (colas max 0, CPU VM 0.10); domina el recorrido y el polling |
| 1MB | 6 | 1 | 3 | 10 | medida | 20s | 0.722 | 1.333 | 1.376 | 295 | 23.52 | 0 | 0 | 0 | 14 | si | ninguno: sin saturacion (colas max 1, CPU VM 0.04); domina el recorrido y el polling |
| 1MB | 6 | 1 | 3 | 50 | medida | 20s | 5.324 | 6.793 | 7.253 | 272 | 75.22 | 0 | 0 | 0 | 3 | si | nodo GKE 10.128.15.218:9100 al 85% de CPU |
| 1MB | 6 | 10 | 1 | 1 | medida | 20s | 1.871 | 1.922 | 1.924 | 14 | 2.46 | 0 | 0 | 0 | 0 | si | ninguno: sin saturacion (colas max 34, CPU VM 0.10); domina el recorrido y el polling |
| 1MB | 6 | 10 | 1 | 10 | medida | 20s | 8.78 | 10.344 | 10.918 | 36 | 15.39 | 0 | 0 | 0 | 1 | si | ninguno: sin saturacion (colas max 19, CPU VM 0.08); domina el recorrido y el polling |
| 1MB | 6 | 10 | 1 | 50 | medida | 20s | 32.496 | 53.524 | 54.149 | 48 | 52.86 | 0 | 0 | 0 | 1 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 6 | 10 | 2 | 1 | medida | 20s | 1.354 | 4.264 | 7.018 | 13 | 2.41 | 0 | 0 | 0 | 0 | si | nodo GKE 10.128.15.218:9100 al 99% de CPU |
| 1MB | 6 | 10 | 2 | 10 | medida | 20s | 7.317 | 9.456 | 9.945 | 38 | 15.43 | 0 | 0 | 0 | 1 | si | ninguno: sin saturacion (colas max 5, CPU VM 0.13); domina el recorrido y el polling |
| 1MB | 6 | 10 | 2 | 50 | medida | 20s | 30.657 | 43.206 | 44.694 | 55 | 52.46 | 0.0984 | 0 | 0 | 2 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 6 | 10 | 3 | 1 | medida | 20s | 1.452 | 1.996 | 2.025 | 16 | 2.45 | 0 | 0 | 0 | 0 | si | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 6 | 10 | 3 | 10 | medida | 20s | 7.261 | 8.598 | 9.022 | 40 | 15.79 | 0 | 0 | 0 | 3 | si | ninguno: sin saturacion (colas max 4, CPU VM 0.08); domina el recorrido y el polling |
| 1MB | 6 | 10 | 3 | 50 | medida | 20s | 32.102 | 46.785 | 51.598 | 61 | 49.27 | 0.0161 | 0 | 0 | 6 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 6 | 50 | 1 | 1 | medida | 20s | 8.175 | 8.209 | 8.212 | 3 | 2.07 | 0 | 0 | 0 | 1 | si | nodo GKE 10.128.15.218:9100 al 91% de CPU |
| 1MB | 6 | 50 | 1 | 10 | medida | 20s | 35.178 | 49.225 | 49.324 | 10 | 11.13 | 0 | 0 | 0 | 1 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 6 | 50 | 1 | 50 | medida | 20s | 23.614 | 32.523 | 33.315 | 2 | 11.97 | 0.7143 | 0 | 0 | 0 | no | nodo GKE 10.128.15.218:9100 al 95% de CPU |
| 1MB | 6 | 50 | 2 | 1 | medida | 20s | nan | nan | nan | 0 | 1.96 | 0 | 0 | 0 | 0 | no | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 6 | 50 | 2 | 10 | medida | 20s | 32.641 | 38.254 | 38.319 | 10 | 12.35 | 0.0909 | 0 | 0 | 0 | no | workers (VMs) por I/O: cola tasks max 121 con CPU 0.09 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 6 | 50 | 2 | 50 | medida | 20s | 39.703 | 42.359 | 42.595 | 2 | 12.79 | 0.8571 | 0 | 0 | 0 | no | workers (VMs) por I/O: cola tasks max 168 con CPU 0.10 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 6 | 50 | 3 | 1 | medida | 20s | 27.902 | 27.902 | 27.902 | 1 | 2.12 | 0 | 0 | 0 | 0 | si | nodo GKE 10.128.15.218:9100 al 100% de CPU |
| 1MB | 6 | 50 | 3 | 10 | medida | 20s | 29.476 | 41.203 | 43.345 | 13 | 10.48 | 0 | 0 | 0 | 0 | si | workers (VMs) por I/O: cola tasks max 148 con CPU 0.07 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
| 1MB | 6 | 50 | 3 | 50 | medida | 20s | 33.461 | 34.687 | 34.796 | 2 | 10.22 | 0.7778 | 0 | 0 | 4 | no | workers (VMs) por I/O: cola tasks max 98 con CPU 0.08 nucleos/VM (fragmentos ida y vuelta a Redis por la red VM-cluster) |
