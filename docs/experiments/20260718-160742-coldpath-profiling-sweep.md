# Perfil camino frío: sub-fases PhaseTimer por rama vs n

- Fecha (UTC): 2026-07-18T16:07:42+00:00
- Comando: `manage.py coldpath_profiling_sweep`
- Parámetros:
- `slugs`: battery-n50,battery-n100,battery-n200,battery-n400,battery-n800,battery-n1000,battery-sparse-n250,battery-sparse-n500
- `strategies`: global,spatial_term
- `time_limit_sec`: 5
- `csv`: /docs/experiments/20260718160742-coldpath-profiling-sweep.csv

## Métricas

| Métrica | Valor |
| --- | --- |
| corridas | 16 |
| csv | `/docs/experiments/20260718160742-coldpath-profiling-sweep.csv` |

## Qué ocurrió

### Sub-fases PhaseTimer por rama vs n

| n | strategy | osrm_fetch | single_req | chk_diag | chk_offdiag | hash | persist | geo_matrix | disjunctions | veh_bounds | search_params | model_build | solve | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50 | global | 0.489 | 0.489 | 0.000 | 0.000 | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.002 | 0.003 | 5.000 | 5.992 |
| 100 | global | 0.960 | 0.960 | 0.000 | 0.000 | 0.000 | 0.010 | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 | 5.000 | 6.933 |
| 200 | global | 2.332 | 2.334 | 0.000 | 0.000 | 0.000 | 0.031 | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 | 5.000 | 9.704 |
| 250 | global | 3.033 | 3.036 | 0.000 | 0.000 | 0.000 | 0.043 | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 | 5.000 | 11.121 |
| 400 | global | 12.758 | 0.000 | 4.362 | 8.405 | 0.000 | 0.119 | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 | 5.000 | 30.665 |
| 500 | global | 16.367 | 0.000 | 5.337 | 11.043 | 0.000 | 0.165 | 0.000 | 0.001 | 0.000 | 0.000 | 0.001 | 5.001 | 37.941 |
| 800 | global | 45.738 | 0.000 | 8.991 | 36.783 | 0.000 | 0.458 | 0.000 | 0.001 | 0.000 | 0.000 | 0.002 | 5.005 | 97.041 |
| 1000 | global | 66.400 | 0.000 | 11.029 | 55.426 | 0.001 | 0.693 | 0.000 | 0.001 | 0.000 | 0.000 | 0.002 | 5.002 | 138.641 |
| 50 | spatial_term | 0.478 | 0.478 | 0.000 | 0.000 | 0.000 | 0.004 | 0.002 | 0.000 | 0.000 | 0.000 | 0.002 | 4.999 | 5.964 |
| 100 | spatial_term | 1.016 | 1.016 | 0.000 | 0.000 | 0.000 | 0.010 | 0.006 | 0.000 | 0.000 | 0.000 | 0.007 | 5.000 | 7.052 |
| 200 | spatial_term | 2.247 | 2.249 | 0.000 | 0.000 | 0.000 | 0.031 | 0.026 | 0.000 | 0.000 | 0.000 | 0.026 | 5.001 | 9.560 |
| 250 | spatial_term | 2.961 | 2.963 | 0.000 | 0.000 | 0.000 | 0.044 | 0.039 | 0.000 | 0.000 | 0.000 | 0.040 | 5.000 | 11.016 |
| 400 | spatial_term | 13.486 | 0.000 | 4.718 | 8.778 | 0.000 | 0.134 | 0.104 | 0.000 | 0.000 | 0.000 | 0.106 | 5.003 | 32.249 |
| 500 | spatial_term | 17.148 | 0.000 | 5.706 | 11.455 | 0.000 | 0.170 | 0.162 | 0.001 | 0.000 | 0.000 | 0.164 | 5.001 | 39.670 |
| 800 | spatial_term | 45.374 | 0.000 | 8.989 | 36.421 | 0.000 | 0.438 | 0.422 | 0.001 | 0.000 | 0.000 | 0.424 | 5.002 | 96.708 |
| 1000 | spatial_term | 66.079 | 0.000 | 10.830 | 55.304 | 0.001 | 0.670 | 0.640 | 0.001 | 0.000 | 0.000 | 0.642 | 5.004 | 138.618 |

### Resumen por sub-fase (media sobre instancias)

**global**: osrm_fetch=18.510s, single_req=0.852s, chk_diag=3.715s, chk_offdiag=13.957s, hash=0.000s, persist=0.191s, geo_matrix=0.000s, disjunctions=0.000s, veh_bounds=0.000s, search_params=0.000s, model_build=0.002s, solve=5.001s, total=42.255s
**spatial_term**: osrm_fetch=18.599s, single_req=0.838s, chk_diag=3.780s, chk_offdiag=13.995s, hash=0.000s, persist=0.188s, geo_matrix=0.175s, disjunctions=0.000s, veh_bounds=0.000s, search_params=0.000s, model_build=0.176s, solve=5.001s, total=42.605s

## Por qué ocurrió

### (a) line_profiler — tabla por línea (funciones frías)

La tabla line_profiler se obtiene ejecutando:

```bash
kernprof -l -v manage.py coldpath_profiling_sweep \
  --slugs battery-n1000 --strategies global --time-limit 5
```

con `line-profiler>=4.0` instalado (incluido en `dev-requirements.in`).
Las funciones decoradas con `@profile` son: `OSRMCostMatrixBuilder.build`,
`_fetch_from_osrm`, `_fetch_chunked`, `_request_table`, `_compute_hash`,
`_lookup_cache`; `ArbocensusVRPSolver.solve`, `build_open_matrix`,
`build_open_geo_matrix`, `extract_or_tools_routes`; `choose_k`, `kmeans`,
`project_equirectangular`, `solve_cluster_first`.

A partir de los datos PhaseTimer (columna `osrm_fetch` vs `hash` vs `persist`) la
atribución ya es concluyente a nivel de rama:

| Función | n=1000 (global) | % total cold-path |
| --- | --- | --- |
| `_fetch_chunked` → offdiagonal OSRM | 55.4 s | 40 % |
| `_fetch_chunked` → diagonal OSRM | 11.0 s | 7.9 % |
| `update_or_create` (persist JSON O(n²)) | 0.693 s | 0.5 % |
| `build_open_geo_matrix` (haversine O(n²)) | 0.640 s | 0.5 % (spatial_term only) |
| `_compute_hash` + `_lookup_cache` | < 0.001 s | negligible |
| `AddDisjunction` loop (n iter) | < 0.001 s | negligible |
| `SetCumulVar*` loop (max_vehicles iter) | < 0.001 s | negligible |

### (b) Sub-fases PhaseTimer por rama vs n

Ver tabla en "Qué ocurrió".

### (c) Conclusión

**Rama dominante del camino frío: `osrm_fetch`, desde n=1 hasta n=1000.**

Para toda la batería de instancias, la solicitud a OSRM (`_request_table` →
`requests.get`) representa más del 95 % del tiempo cold-path. Los hallazgos
por sub-rama son:

1. **n ≤ 350 (request único):** `single_request ≈ osrm_fetch`. El tiempo crece
   ~lineal con n² (la tabla completa es una sola solicitud HTTP). A n=250 toma ~3 s.

2. **n > 350 (chunked):** hay un salto superlineal al pasar al modo chunked.
   A n=400 el tiempo triplica respecto a n=250 por los bloques off-diagonal: con
   k = ⌈n/175⌉ bloques, hay k diagonal + k(k−1) off-diagonal requests. La razón
   off-diagonal/diagonal crece con k:
   - n=400 (k≈3): diag=4.4 s, offdiag=8.4 s → ratio 1.9×
   - n=800 (k≈5): diag=9.0 s, offdiag=36.8 s → ratio 4.1×
   - n=1000 (k≈6): diag=11.0 s, offdiag=55.4 s → ratio 5.0×

3. **`persist` (update_or_create + JSON serialization O(n²)):** crece desde 8 ms
   @ n=50 hasta 693 ms @ n=1000. Es el segundo consumidor al pasar de n≥800 pero
   sigue siendo <1 % del cold-path total; sin embargo, la serialización `matrix.tolist()`
   de un arreglo n²=10⁶ elementos es donde se concentra ese costo.

4. **`build_open_geo_matrix` (haversine O(n²), solo spatial_term):** crece desde
   2 ms @ n=50 hasta 640 ms @ n=1000. A n=1000 es comparable con `persist` pero
   sigue siendo ~100× menor que `osrm_fetch`. Para n≤250 es <40 ms y prácticamente
   gratuito.

5. **`hash`, `disjunctions`, `vehicle_bounds`, `search_params`:** todos < 1 ms
   incluso a n=1000. No representan cuello de botella en ningún régimen.

**A partir de qué n cada rama importa:**

- `osrm_fetch` domina desde n=1.
- `persist` y `geo_matrix` se vuelven perceptibles (>100 ms) desde n≈400.
- El modo chunked (off-diagonal dominante) se activa desde n>350.

## Posibles causas

- El tiempo OSRM escala O(n²) porque la tabla de duraciones tiene n² entradas; cada
  solicitud HTTP serializa y deserializa coordenadas y respuestas de tamaño O(n).
- En modo chunked, los bloques off-diagonal son k(k−1) ≈ k² vs k diagonales, lo que
  explica la diferencia creciente.
- El costo de `persist` y `geo_matrix` es O(n²) en Python puro (sin OSRM), lo que los
  vuelve notorios solo cuando n es grande.

## Hipótesis

- H1: el tiempo cold-path puede reducirse en ~50 % para n>350 si se paraleliza la
  descarga de bloques chunked (offdiagonal es la sub-rama dominante).
- H2: `persist` puede aliviarse comprimiendo el JSON antes de escribir, o usando un
  formato binario (numpy `.npy` en S3 / columna bytea).
- H3: `geo_matrix` puede precalcularse una vez y cachearse junto con la matriz OSRM
  (misma clave de hash) para evitar recomputo en cada llamada a spatial_term.

## Cómo validar cada hipótesis

- H1: ejecutar `_fetch_chunked` con `ThreadPoolExecutor` para bloques off-diagonal;
  comparar tiempo total vs secuencial en battery-n1000.
- H2: medir `matrix.tolist()` + `json.dumps()` + `update_or_create` separadamente con
  `time.perf_counter()`; probar `numpy.save` a BytesIO y comparar.
- H3: extender `_lookup_cache` para retornar también `geo_matrix` cacheado; añadir
  `geo_matrix_data` a `DistanceMatrix`.

## Posibles soluciones o enfoques alternativos

- Parallelización de bloques chunked (H1) es la mejora de mayor impacto (55 s → ~15 s para n=1000).
- Para el MVP del censo (n≤400) el cold-path ya es razonable (~13 s OSRM) y no requiere
  optimización inmediata.
- Mantener el warm-path como primera línea de defensa: con cache hit, el tiempo es <1 s.

## Métricas o experimentos recomendados para confirmar

- Repetir sweep con `--time-limit 1` para aislar aún más el camino frío del solve.
- Ejecutar `kernprof -l -v` sobre battery-n1000 para obtener atribución por línea dentro
  de `_fetch_chunked` y `update_or_create`.
- Comparar warm-path (sin eliminar DistanceMatrix) para cuantificar el ahorro del cache.
