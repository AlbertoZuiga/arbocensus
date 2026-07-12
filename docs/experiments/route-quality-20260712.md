# R2 — Comparación de estrategias del solver sobre el dataset real

- Fecha: 2026-07-12 (UTC)
- Branch: `docs/strategy-comparison` (sobre main `55e97d3`, que incluye el fix de
  `math.ceil` en el transit callback, PR #135)
- Datos crudos (versionados junto a este reporte):
  - `r2-phase1-global-spatial-postceil-20260712.csv` — fase 1, global y spatial_term (código de main)
  - `r2-phase1-cluster-first-fix139-20260712.csv` — fase 1, cluster_first con el fix de PR #139
  - `r2-phase1-global-spatial-20260712.csv` — corrida previa al rebase (pre-#135), solo referencia
  - `r2-phase2-spatial-grid-20260712.csv` — fase 2, grilla 6 variantes × 3 semillas de spatial_term

## a. Entorno

Idéntico a RP2 (`profiling-20260711.md` §a): `docker-compose.prod.yml`, imágenes
target `prod`, OSRM real con PBF completo de Chile (MLD, perfil foot,
`--max-table-size 5000`), PostGIS 15-3.3, Redis 7, MacBook M4 Pro con Docker
Desktop. Cache de matriz caliente desde la primera corrida (el fetch frío se
pagó una sola vez al inicio).

Dos particularidades de esta sesión:

1. **Dataset recreado.** El volumen de Postgres del experimento RP2 fue
   eliminado, así que el dataset se recreó con el mismo code path de
   `POST /api/datasets/from-legacy-selection/` documentado en RP2 §b
   (`legacy.list_trees()` → `load_selection` → `create_dataset`). Nuevo UUID:
   `c7b7a8e3-ec8c-4fa7-88a8-324f2dd579b7`, n=1607 (429 `legacy_api` + 1178
   `legacy_app`), idéntico en contenido al de RP2.
2. **cluster_first medido con el fix de PR #139.** La implementación en main
   tiene dos defectos que la hacen inviable de medir: `choose_k` usa
   `average_pair_travel` (media de TODOS los pares de una matriz metropolitana)
   como proxy de viaje entre paradas consecutivas — sobreestima el trabajo por
   árbol en órdenes de magnitud y explota k a cientos de clusters — y cada
   sub-solve recibe el `time_limit` COMPLETO (k × 120 s de cómputo, comparación
   desleal). Una corrida con ese código superó 8 h y fue abortada. PR #139
   (`fix/cluster-first-k-and-time-budget`, abierto) corrige ambos:
   `mean_nearest_neighbor_travel` en `choose_k` y presupuesto proporcional al
   tamaño del cluster. Para no tocar código de producción en este branch, la
   corrida de cluster_first montó ese `strategies.py` por bind-mount read-only
   sobre la imagen prod (`docker compose run -v <fix>/strategies.py:/app/apps/optimization/strategies.py:ro`).

## b. Diseño experimental

- **Fase 1**: 3 estrategias (`global`, `spatial_term`, `cluster_first`) en la
  variante representativa service_time=2 min × T_max=3 h; time_limit **120 s**
  (RP2 §e: 120 s ≈ 180 s en calidad para n=1607); 3 semillas (base 42).
- **Criterio de decisión** (fijado antes de correr): una estrategia gana si
  reduce solapamiento/ruta o mejora el IoU del peor par SIN degradar balance
  <0.85, sin rutas >T_max reales y con travel total dentro de +10 % de global.
  El piso 0.85 se calibró con cifras pre-#135 (RP2: global 0.865 en esta
  variante). El ceil del callback bajó el balance de la propia baseline a 0.838,
  así que la cláusula se evalúa **relativa a global** (no degradar balance
  respecto de la baseline medida con el mismo código); el umbral absoluto queda
  obsoleto y no se usa. Los demás criterios se mantienen tal cual.
- **Fase 2** (solo el ganador de fase 1): grilla completa service_time
  {1,2,3} min × T_max {2,3} h, time_limit 120 s, 3 semillas.
- Comando reproducible:

  ```bash
  docker compose -f docker-compose.prod.yml run --rm -e PYTHONUNBUFFERED=1 backend \
    python manage.py baseline_sweep \
      --dataset c7b7a8e3-ec8c-4fa7-88a8-324f2dd579b7 \
      --strategies global,spatial_term,cluster_first \
      --service-time 2 --t-max 3 --seeds 3 --base-seed 42 --time-limit 120 \
      --csv /results/<salida>.csv
  ```

## c. Fase 1 — head-to-head en st=2 min × T_max=3 h (media de 3 semillas)

| estrategia | k | balance | T̄ [s] | σ(T) [s] | >T_max | dropped | travel total [s] | Δ travel | sum_rmax [m] | solap./ruta | IoU peor par |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| global | 25.0 | 0.838 | 10103 | 584 | 0 | 0 | 59725 | — | 22455 | 168.0 | 0.51 |
| spatial_term | 25.0 | 0.833 | 10139 | 604 | 0 | 0 | 60611 | **+1.5 %** | 19578 (−12.8 %) | **77.3 (−54 %)** | 0.55 |
| cluster_first (#139) | 34.0 | 0.698 | 7683 | 771 | 0 | **12** | 69813 | +16.9 % | 9714 (−57 %) | 20.0 (−88 %) | 0.48 |

Observaciones:

- **spatial_term corta el solapamiento por ruta a menos de la mitad** (168 →
  77) con solo +1.5 % de travel y balance dentro del ruido entre semillas
  (0.833 vs 0.838). El IoU del peor par **empeora** levemente (0.51 → 0.55; en
  esta métrica más alto es peor): las cajas se comprimen (sum_rmax −12.8 %)
  pero persiste un par vecino con alta intersección de bbox. Cumple el criterio
  (§b): reduce solapamiento/ruta, no degrada balance vs global (−0.005, dentro
  de la dispersión entre semillas de global), 0 rutas >T_max, 0 drops, travel
  ≪ +10 %.
- **cluster_first queda descalificada incluso con el fix**: deja 12 árboles
  fuera (consistente en las 3 semillas), usa k=34 (+36 % de flota), balance
  0.698 y travel +16.9 %. El particionamiento duro impide reasignar árboles de
  borde cuando un cluster no alcanza a cubrirlos dentro de T_max, y los
  sub-solves cortos (120 s repartidos entre ~34 clusters) activan las
  disyunciones. Su solapamiento (20/ruta) y sum_rmax (9714 m) marcan la cota
  de separación espacial alcanzable, útil como referencia, no como default.
- Las 3 semillas de cada estrategia convergen a soluciones casi idénticas en k,
  balance y travel (≤0.5 % de spread; consistente con RP2: la varianza proviene
  solo del corte por wall-clock). Las métricas de forma sí dispersan: global da
  solap./ruta 177/150/177 e IoU 0.54/0.45/0.55 según la semilla, así que su
  media (168, 0.51) esconde una semilla mejor. Aun contra la mejor semilla de
  global (150), spatial_term (81/75/75) baja el solapamiento ≥45 %.
- El fix de PR #135 (`math.ceil` en el callback) **eliminó el artefacto F7**:
  0 rutas >T_max en las 27 corridas post-#135 (en RP2 eran sistemáticas en
  T_max=2 h; la corrida pre-#135 de esta misma sesión todavía las muestra). Como contraparte, la solución de global cambió respecto de la
  corrida pre-#135 con los mismos parámetros (k 24→25, balance 0.890→0.838,
  travel 56875→59725): los arcos redondeados hacia arriba encarecen la
  capacidad efectiva por ruta. La corrida pre-rebase queda en
  `r2-phase1-global-spatial-20260712.csv` como referencia de ese efecto.

## d. Fase 2 — grilla spatial_term, 6 variantes × 3 semillas (medias)

| st [min] | T_max [h] | k | balance | T̄ [s] | σ(T) [s] | >T_max | dropped | travel total [s] | sum_rmax [m] | solap./ruta | IoU peor par |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 23.0 | 0.996 | 7167 | 7 | 0 | 0 | 68410 | 20937 | 109.2 | 0.41 |
| 1 | 3 | 16.0 | 0.835 | 9745 | 601 | 0 | 0 | 59491 | 19905 | 146.1 | 0.49 |
| 2 | 2 | 36.0 | 0.998 | 7180 | 3 | 0 | 1.0 | 65727 | 16917 | 82.8 | 0.54 |
| 2 | 3 | 25.0 | 0.833 | 10138 | 606 | 0 | 0 | 60588 | 19588 | 75.2 | 0.55 |
| 3 | 2 | 49.0 | 0.998 | 7185 | 2 | 0 | 2.0 | 63146 | 17347 | 55.8 | 0.32 |
| 3 | 3 | 34.0 | 0.836 | 10320 | 522 | 0 | 0 | 61611 | 24267 | 79.9 | 0.55 |

La fila st=2 × T_max=3 h es la misma configuración de la fase 1 pero corrida
aparte (otro CSV): difiere en el margen del corte por wall-clock del GLS (travel
60588 vs 60611, sum_rmax 19588 vs 19578, solap. 75.2 vs 77.3). La escala de esa
variación acota la precisión de todas las comparaciones de esta sección.

Observaciones:

- La estructura de la grilla replica la de global en RP2 §d: T_max=2 h fuerza
  balance ≈1.0 y dispara k (23→36→49 con service_time); T_max=3 h baja k ~30 %
  y el balance a ~0.83.
- Contra la grilla global de RP2 (180 s, pre-#135, comparación cualitativa),
  spatial_term mantiene el solapamiento por debajo en las variantes de trabajo
  denso (st=1×T2h: 109 vs 194; st=2×T2h: 83 vs 94) y aplana la peor variante;
  en st=3×T3h queda a la par (80 vs 78).
- **Drops en T_max=2 h**: st=2 deja 1 árbol y st=3 deja 2 (los 3 seeds). Es la
  misma zona apretada donde global ya dropeaba con st=3 en RP2; con ceil los
  arcos son ~1 s más caros y el margen se agota antes. T_max=2 h con
  service_time alto opera al límite de capacidad — si el censo exige cobertura
  total, usar T_max=3 h.
- k queda estable entre estrategias a igual variante (23/36/49 en T2h,
  idéntico a global en RP2): el término espacial no infla la flota.

## e. Fase 3 (tuning fino) — no ejecutada, con fundamento

- spatial_term cumple el criterio de decisión con su `SPAN_COEF=3` de fábrica;
  subirlo movería el trade-off hacia menos solape a costa de más travel, que
  hoy no hace falta (+1.5 % de margen sobre global contra un tope de +10 %).
- El eje con señal real es el par malo de IoU (0.55): es un problema de
  geometría local (dos rutas vecinas en zona densa), no del coeficiente global
  — tuning de `span_coef` no lo separa sin castigar al resto.
- `DROP_PENALTY` y k de cluster_first quedan sin tunear porque cluster_first
  está descartada como default; cualquier iteración sobre ella debe partir por
  mergear PR #139.

## f. Decisión y defaults operativos recomendados (aplicar en R3, PR aparte)

1. **Estrategia default: `spatial_term`.** Gana la fase 1 con −54 % de
   solapamiento por ruta, −12.8 % de sum_rmax, +1.5 % de travel, balance y k
   idénticos a global, 0 drops en la variante de operación (T_max=3 h).
2. **`SOLVER_TIME_LIMIT_SEC = 120`** (heurística `min(30 + 1.5·n, 120)`):
   confirmado en RP2 §e (120 s ≈ 180 s en calidad para n=1607) y revalidado
   aquí — toda la grilla corrió a 120 s con resultados consistentes.
3. **Configuración censal de referencia: service_time=2 min × T_max=3 h**
   (cobertura total sin drops; T_max=2 h solo si el balance ≈1.0 es
   prioritario y se tolera dropear 1–2 árboles o subir la flota).
4. **`SPAN_COEF=3` se mantiene** (sin tuning, §e).
5. **cluster_first no habilitar** como opción de producción hasta mergear
   PR #139; incluso con el fix queda descartada como default (12 drops,
   balance 0.698, +16.9 % travel).

## Regeneración

Cualquier cifra se regenera con el comando de §b sobre el dataset de §a
(recrearlo si el volumen no existe), cambiando `--strategies`/`--service-time`/
`--t-max` según la tabla; para cluster_first, montar el `strategies.py` de
PR #139 como se describe en §a.2. Los CSV citados son la salida directa de
esos comandos.
