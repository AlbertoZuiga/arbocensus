# Corrida de referencia unificada (`reference-n1607`, 2026-08-02)

**Objetivo:** producir en UNA sola corrida todas las magnitudes que la Tabla de métricas de la
Sección 4.1.2 de la tesis componía desde corridas distintas (rutas bajo `T_min`, tiempo extremo a
extremo y auto-cruces sobre calle venían de tres corridas ajenas a la de referencia), de modo que la
tabla deje de ser una composición declarada.

**Método:** `manage.py baseline_postpass --dataset reference-n1607 --strategy spatial_term
--seeds 42,43,44 --cold-first --csv docs/experiments/reference-unified-20260802.csv`.
Configuración de producción: estrategia `spatial_term`, límite de solver 120 s, `T_min` 7200 s,
`T_max` 10800 s, servicio 2 min, post-proceso 2-opt activo (default del pipeline). El flag
`--cold-first` (agregado en este ciclo) borra la matriz de costos cacheada antes de la primera
semilla, de modo que la repetición 42 mide el tiempo extremo a extremo con caché fría y las
repeticiones 43 y 44 lo miden con caché caliente. El comando instrumenta además, por semilla:
rutas bajo `T_min`, rutas sobre `T_max`, árboles descartados, desviación estándar de duraciones y
`crossings_road` (auto-cruces contados sobre la polilínea real de calles que devuelve OSRM, la
misma geometría que dibuja el mapa del censista).

## Resultado (una fila por semilla)

| semilla | k | drops | travel_sec | balance | σ rutas [s] | rutas > T_max | rutas < T_min | crossings_road | wall clock [s] | caché |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 25 | 0 | 59 718 | 0,836 | 555 | 0 | 0 | 24 | 334,6 | fría |
| 43 | 25 | 0 | 56 722 | 0,837 | 526 | 0 | 0 | 37 | 122,9 | caliente |
| 44 | 25 | 0 | 58 696 | 0,829 | 612 | 0 | 0 | 33 | 123,7 | caliente |

Promedios sobre las tres semillas: desplazamiento 58 379 s, tiempo promedio por ruta 10 048 s
(≈ 2 h 47 min), desviación estándar media 564 s (5,6 % del promedio), auto-cruces sobre calle
31,3 (24–37 según la repetición). Tiempo de reloj con caché caliente: 122,9 y 123,7 s
(media 123,3 s); con caché fría 334,6 s, donde la diferencia (~211 s) es la construcción de la
matriz de costos contra OSRM.

## Diferencias contra las cifras compuestas que reemplaza

- **Rutas bajo `T_min`: 0 en las tres semillas.** La cifra compuesta que citaba la tesis (3) venía
  de `penalty-sensitivity-20260713-reference.csv` (columna `tmin_gap_routes`), una corrida de julio
  con otro estado del código. En esta corrida ninguna ruta queda bajo el piso; se publica la cifra
  medida.
- **Tiempo extremo a extremo con caché fría: 334,6 s, sobre el umbral de 300 s de CA-05.** La
  corrida de julio (`20260713-real-case-metrics-spatial.csv`) medía 299,3 s. El criterio CA-05 se
  enuncia sobre el caso con caché (123,3 s, con holgura), pero el primer cálculo de un dataset
  nuevo queda ahora por sobre los 5 min en esta máquina, no "al borde": se reporta tal cual.
- **Auto-cruces sobre calle: 31,3 de media (24–37).** La corrida del 30-07
  (`reference-n1607-20260730.csv`) midió 40/40/33. Mismo orden de magnitud; la dispersión entre
  semillas domina.
- Desplazamientos (59 718 / 56 722 / 58 696, media 58 379) y balance (0,829–0,837) quedan casi
  idénticos a la corrida de referencia de julio (59 690 / 56 707 / 58 696, media 58 364): la
  replicación por permutación de nodos es estable en estas magnitudes.

## Reserva de instrumento

`t_matrix_sec` del CSV suma timers de chunks que OSRM sirve en paralelo, por lo que puede exceder
el tiempo de reloj (422 s frente a 334,6 s en la semilla fría); es la misma duplicación de timers
anidados ya documentada en el perfil del droplet. Para el costo de la matriz debe citarse la
diferencia entre wall clock frío y caliente, no esa columna.

## Acción

- La Tabla de métricas de la Sección 4.1.2 se reescribe con estas cifras y pierde sus tres notas de
  composición; el Anexo 3 pasa a citar este CSV como fuente única de la corrida de referencia.
- CA-05 se acredita con 123,3 s (caché caliente, caso de operación normal) y la lectura del caso
  frío se corrige: 334,6 s, por sobre el umbral, contra los 299,3 s de julio.
