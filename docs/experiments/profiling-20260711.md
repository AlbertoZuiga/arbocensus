# Profiling del pipeline de optimización (6 variantes de duración)

- Fecha: 2026-07-11/12 (UTC)
- Branch: `experiment/solver-profiling-6-variants` (sobre PR #125, que aporta el harness `baseline_sweep`)
- Datos crudos (versionados junto a este reporte):
  - `profiling-grid-full-20260711.csv` — grilla 6 variantes × 3 semillas, dataset completo (n=1607)
  - `profiling-grid-small-20260711.csv` — misma grilla, área chica (n=157)
  - `profiling-tl60-full.csv`, `profiling-tl120-full.csv` — sensibilidad a `time_limit`
  - `pilot-full.csv` — corrida piloto en frío (cache de matriz vacía)

## a. Entorno

No existe deploy real de producción; se replicó producción localmente con
`docker-compose.prod.yml` (nuevo en este branch): imágenes construidas con el
target `prod` del Dockerfile (sin bind-mounts de código, sin hot-reload,
usuario no root), OSRM real con el PBF completo de Chile
(`data/osm/chile-latest.osm.pbf`, preprocesado MLD, perfil foot,
`--max-table-size 5000`), PostGIS 15-3.3 y Redis 7.

**Diferencias explícitas respecto de un deploy real:**

| Aspecto | Este experimento | Deploy real |
| --- | --- | --- |
| Hardware | MacBook M4 Pro (12 cores, 24 GB), Docker Desktop | VPS/cloud x86, recursos menores |
| Arquitectura | backend/celery nativos arm64; db y osrm `linux/amd64` emulados (Rosetta) | todo nativo x86 |
| Red a OSRM/DB | red interna de compose en la misma máquina (latencia ~0) | red de datacenter; encarece `cost_matrix.osrm_fetch` (100 requests HTTP para n=1607) |
| Punto de entrada | `manage.py baseline_sweep` dentro del contenedor prod, secuencial | API → Celery worker (`--concurrency=2`); mismo code path (`OptimizationPipeline.run`), solo agrega latencia de cola |
| Mount `/results` | bind-mount rw para extraer CSV/markdown | no existe; no está en ningún code path medido |

Versiones: Python 3.12.11, Django 6.0, ortools 9.15.6755, numpy 2.4.6.

## b. Dataset

Definitivo (ambas fuentes legacy, import de PR #112):

- **Completo**: "Profiling - legacy completo (ambas fuentes)", **n=1607**
  (429 `legacy_api` + 1178 `legacy_app` con mediana de posición por QR).
  Creado con el mismo code path que `POST /api/datasets/from-legacy-selection/`:

  ```python
  from apps.datasets import legacy
  rows = legacy.list_trees()
  loaded = legacy.load_selection([(r["source"], r["external_id"]) for r in rows])
  legacy.create_dataset("Profiling - legacy completo (ambas fuentes)", loaded)
  ```

- **Área chica** (sensibilidad a n): área legacy 40 vía `legacy.import_area(40)`, **n=157**.

## c. Diseño experimental

- 6 variantes obligatorias: service_time {1,2,3} min × T_max {2,3} h; `min_route_time_sec = min(7200, T_max)`.
- Estrategia: `global` (default de producción; sin cruce con las otras 2 estrategias, recorte autorizado).
- 3 semillas (42–44). El solver de OR-Tools es determinista dados los parámetros;
  la semilla etiqueta la repetición y la varianza observable proviene del corte
  por wall-clock del GLS (ver `solve_sd` abajo) — en variantes donde GLS agota
  el presupuesto, las 3 repeticiones convergen a soluciones casi idénticas.
- **time_limit fijado ANTES de la grilla: 180 s** = exactamente lo que produce la
  heurística de producción (`min(30 + 1.5·n, SOLVER_TIME_LIMIT_SEC=180)`) para
  n=1607. Presupuesto real: 18 corridas × ~2–3 min ≈ 40 min (grilla completa).
- Comando reproducible (harness `baseline_sweep`, PR #125):

  ```bash
  docker compose -f docker-compose.prod.yml run --rm backend \
    python manage.py baseline_sweep \
      --dataset <uuid> --strategies global \
      --service-time 1,2,3 --t-max 2,3 --seeds 3 --time-limit 180 \
      --csv /results/profiling-grid-full-20260711.csv
  ```

## d. Resultados — dataset completo (n=1607), media de 3 semillas

| st [min] | T_max [h] | k | balance | T̄ [s] | σ(T) [s] | rutas >T_max | dropped | travel total [s] | solap./ruta | IoU peor par | solve [s] (±sd) | total [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 23.0 | 0.992 | 7229 | 14 | 21.7 | 0 | 69868 | 194.0 | 0.65 | 92.8 ±63.8 | 93.4 |
| 1 | 3 | 15.0 | 0.877 | 10417 | 378 | 1.0 | 0 | 59843 | 182.5 | 0.47 | 89.0 ±3.6 | 89.6 |
| 2 | 2 | 36.0 | 0.996 | 7219 | 6 | 35.0 | 0 | 67047 | 93.6 | 0.48 | 131.6 ±34.4 | 132.2 |
| 2 | 3 | 24.0 | 0.865 | 10399 | 391 | 1.0 | 0 | 56750 | 97.5 | 0.42 | 126.9 ±6.7 | 127.5 |
| 3 | 2 | 49.0 | 0.998 | 7213 | 3 | 49.0 | 1.0 | 64360 | 57.0 | 0.41 | 139.2 ±14.1 | 139.8 |
| 3 | 3 | 33.0 | 0.890 | 10554 | 284 | 2.3 | 0 | 59023 | 78.2 | 0.38 | 49.3 ±14.1 | 49.8 |

(sd de solve = desviación estándar poblacional sobre las 3 semillas.)

Observaciones:

- **k escala fuerte con service_time bajo T_max=2h** (23 → 36 → 49): el trabajo de
  servicio domina la capacidad de cada ruta.
- **T_max=2h produce "excesos" sistemáticos** (~todas las rutas 13–30 s sobre
  T_max en tiempo estimado). No es infactibilidad del solver: el callback del
  solver trunca cada arco con `int(travel + service)` mientras que la métrica
  estimada suma en float; con ~30–70 arcos por ruta el redondeo acumula
  10–70 s. Artefacto de redondeo, no bug de restricción (la cota dura del
  solver se respeta en su propia aritmética entera).
- **Único drop**: st=3 min × T_max=2h deja 1 árbol fuera (consistente en las 3
  semillas) — la variante más apretada.
- balance ≈1.0 en T_max=2h (min=max=7200 fuerza rutas idénticas); en T_max=3h
  el balance cae a ~0.87 con σ(T) ~300–400 s.

### Desglose por fase (n=1607, cache de matriz caliente; media de las 18 corridas)

| Fase | tiempo [s] | % del total |
| --- | --- | --- |
| cost_matrix (cache_lookup) | 0.57 | 0.5 % |
| model_build | <0.01 | ~0 % |
| solve.first_solution | 1.4 | 1.3 % |
| solve.metaheuristic (GLS) | 103.4 | **98.1 %** |
| solution_extraction | 0.01 | ~0 % |
| metrics | 0.02 | ~0 % |
| **pipeline total** | **105.4** | 100 % |

### Corrida en frío (cache de matriz vacía, piloto st=2×T_max=3)

| Fase | tiempo [s] | % |
| --- | --- | --- |
| cost_matrix.osrm_fetch | 170.8 | **97.6 %** |
| cost_matrix (assembly+lookup) | 0.2 | 0.1 % |
| solve | 3.9 | 2.2 % |
| resto | <0.05 | ~0 % |
| **pipeline total** | **174.9** | 100 % |

(El GLS de esa corrida terminó a los 3.9 s; el rango observado en la grilla es
29–180 s para el mismo dataset: GLS a veces agota el presupuesto y a veces
corta antes.)

## e. Cuellos de botella

1. **Ranking**: en frío, `cost_matrix.osrm_fetch` (97.6 %); en caliente,
   `solve.metaheuristic` (98.1 %). Todo lo demás (`model_build`, extracción,
   métricas, lookup de cache) es ruido (<2 % combinado). El fetch en frío ocurre
   una vez por dataset (cache `DistanceMatrix` por hash de árboles); toda corrida
   posterior es solve-bound.

2. **Sensibilidad a n** (área chica n=157 vs completo n=1607):
   - `osrm_fetch` frío: 1.7 s → 170.8 s (~100× para 10× n, ≈(1607/157)²:
     consistente con O(n²) celdas). El chunking por longitud de URL (175 coords
     por bloque) convierte n=1607 en 10×10 = 100 requests `/table`, cada una con
     ~350 coordenadas. Es el eje que peor escala.
   - `solve.first_solution`: 0.02 s → 1.4 s (~63×).
   - `solve.metaheuristic`: NO escala monótono con n a presupuesto fijo — en
     n=157 el GLS agota los 180 s en casi todas las variantes (media 167 s),
     mientras que en n=1607 corta antes en varias (media 103 s). El límite de
     wall-clock enmascara el costo por iteración; lo que sí crece con n es el
     costo de cada vecindario, no el tiempo total observado.
   - Datos: `profiling-grid-small-20260711.csv`.

3. **Sensibilidad del cuello dominante a time_limit** (st=2×T_max=3, n=1607):

   | time_limit [s] | k | balance | travel total [s] | Δ travel vs 60 s |
   | --- | --- | --- | --- | --- |
   | 60 | 24 | 0.867 | 61521 | — |
   | 120 | 24 | 0.865 | 56830 | −7.6 % |
   | 180 (grilla) | 24 | 0.865 | 56750 | −7.8 % |

   k y balance quedan fijos desde 60 s; la mejora de travel entre 120 s y 180 s
   es 0.1 %. **Para n=1607 un time_limit de 120 s captura ~99 % de la mejora** —
   insumo directo para el experimento de comparación de estrategias
   (`route-quality-20260712.md`, tuning) y para bajar el costo de corridas de
   producción un 33 % sin pérdida medible.

## Conclusiones para §3 de la tesis

- El pipeline es **solve-bound** en operación normal y **OSRM-bound** solo en el
  primer contacto con un dataset; optimizar `model_build`/métricas no tiene valor.
- El presupuesto del GLS es el parámetro de operación dominante: 120 s ≈ 180 s
  en calidad para el dataset definitivo (n=1607).
- La grilla de 6 variantes muestra el trade-off central: T_max=2h maximiza
  balance (≈1.0) pero dispara k y el solapamiento por ruta; T_max=3h reduce
  travel total ~10 % y k ~35 % a costa de balance ~0.87.
- Los "excesos de T_max" reportados son un artefacto de truncamiento entero del
  callback (10–70 s por ruta); si se quiere eliminar, un fix chico es redondear
  hacia arriba (`math.ceil`) en el callback — se deja para un PR aparte.

## Regeneración

Cualquier cifra de este reporte se regenera con los comandos de la sección c
(cambiando `--time-limit`/`--dataset` según tabla) sobre los datasets de la
sección b; los CSV citados son la salida directa de esos comandos.
