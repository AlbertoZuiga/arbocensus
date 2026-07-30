# Optimización de rutas — referencia técnica

## §1 Estrategias

El solver soporta tres estrategias (`RoutingSolution.Strategy`):

| Valor | Descripción |
|---|---|
| `global` | VRP puro, minimiza caminata total. |
| `spatial_term` | VRP + penalización de span geográfico (por defecto `SPATIAL_SPAN_COEF=3`). Reduce entrecruzamiento de rutas. |
| `cluster_first` | k-means → VRP por cluster. Refutada experimentalmente; disponible solo para sweeps de investigación mediante argumento explícito `strategy=cluster_first`. |

La **estrategia por defecto de producción es `spatial_term`** (no `global`). El fanout de producción corre `global` y `spatial_term` y el criterio de recomendación elige al ganador. Un job `compare` (modo investigación) corre las tres.

## §2 Límite de tiempo del solver

```
time_limit = min(30 + 1.5 × n, 120)   [segundos]
```

`n` = árboles activos del dataset. El techo es 120 s.

## §3 Post-pass de re-secuenciado

`resequence_routes` (2-opt intra-ruta) corre siempre dentro de `_persist_solution`, antes de guardar la solución en base de datos. Baja travel y cruces sin coste extra de solver.

## §4 Presets de configuración (`config_presets.py`)

| Clave | Label | `time_span_coef` | `arc_coef` | Descripción |
|---|---|---|---|---|
| `default` | Equilibrada | 0 | 1 | Precios de producción. Punto de partida. |
| `temporal_span_100` | Rutas más parejas | 100 | 1 | Iguala duración entre rutas. Suele agregar caminata. |
| `arc_linear_30` | Menos zigzag | 0 | 30 | Penaliza tramos largos. Sirve cuando sobra tiempo. |

## §5 Fanout de jobs por POST

### Default (`full_comparison=false`)

Un POST a `/api/optimization/jobs/` crea un job por par de `strategies.PRODUCTION_JOB_PAIRS` = `CONFIG_PRESETS × PRODUCTION_STRATEGIES` (fuente única; `views.py` y `recommendation_census` la leen de ahí), cada uno con estrategia explícita: **6 jobs**, los 3 presets × {`global`, `spatial_term`}. Cada job corre una sola estrategia (`pipeline.run(strategy=...)`).

**Por qué 6 y no 4 ni 9** (medido 2026-07-30 sobre los 16 datasets reales con las 9 celdas presentes en todos):

| fanout | solves | costo de travel vs. la ganadora del abanico completo | datasets afectados |
|---|---|---|---|
| 6 pares (actual) | 6 | **0,00 %** | 0 de 15 |
| 4 pares (solo `spatial_term` en los presets alternos) | 4 | +0,35 % medio, +2,54 % peor | 4 de 15 |

Podar `cluster_first` es gratis: en los 2 datasets donde "ganó", otra celda empata su travel y solo se llevó el desempate por `id`; su balance está 0,21–0,24 bajo el control. Podar las celdas `× global` de los presets alternos sí cuesta: `temporal_span_100 × global` gana 3 datasets y `arc_linear_30 × global` gana 1.

**Trampa del census** (`python manage.py recommendation_census`): tabula sobre las soluciones persistidas del último sweep de cada dataset, así que **la tasa de victorias solo significa algo si todas las celdas corrieron en todos los datasets**. Antes del barrido del 2026-07-30, 13 de 16 datasets tenían una sola solución y `default × spatial_term` "ganaba" 14/16 por walkover; con el abanico completo gana 1/16 y es la celda más lenta (todas las demás están −3,8 % a −6,4 % de travel contra ella). Leer `datasets_appearing` antes de cualquier conclusión.

Además la tasa de victorias no puede juzgar a un preset que compra parejura pagando travel: el criterio está dominado por travel, así que pierde por construcción. Para eso están `mean_travel_delta_pct_vs_control` y `mean_balance_delta_vs_control`.

El comando falla (`CommandError`) si la mejor celda **dentro** del fanout cede travel contra la ganadora del abanico completo en algún dataset. Mide costo, no identidad: un empate exacto que la celda podada gana por `id` no cuesta nada y no bloquea. Los datasets que botan todos sus árboles en todas las celdas se reportan aparte — no informan nada.

### Modo investigación (`full_comparison=true`)

Pasar `full_comparison: true` en el body restaura el abanico original: 3 presets × `COMPARE` = 9 solves (incluyendo `cluster_first`).

## §6 Criterio de recomendación (`recommendation.py`)

Orden lexicográfico estricto:

1. `dropped_trees` ascendente (0 primero)
2. `degenerate_routes` ascendente
3. `balance_below_gate` (balance < 0.60) ascendente
4. `total_travel_time_sec` ascendente
5. `total_routes` ascendente
6. `id` (total order, desempate determinístico)

### Regla de empate técnico

Si la solución control (`default×spatial_term`) pasa **las mismas compuertas** que la primera candidata del orden estricto (pasos 1–3: drops, rutas degeneradas, balance) y su viaje difiere menos de **3 %**, gana el control. Esto evita que un desempate arbitrario por `id` cambie la recomendación entre sweeps cuando dos soluciones son prácticamente equivalentes.

La comparación de compuertas no es opcional: sin ella la regla de empate revierte el orden lexicográfico y un control que bota árboles podría recomendarse frente a una solución limpia por una diferencia de viaje de 1 %.

### Supuesto de nómina

El criterio minimiza `total_travel_time_sec` asumiendo que **los censistas se pagan por hora**: menos caminata = menor costo total. Si el pago fuera por jornada/turno, el costo real relevante sería `k = total_routes`, que hoy participa solo como desempate secundario (paso 5 del orden).

## §7 Campos del serializer relacionados

| Campo | Descripción |
|---|---|
| `recommended` | `true` si es la solución recomendada del dataset (según criterio + regla de empate). |
| `travel_margin_pct` | `(travel_propio − travel_recomendada) / travel_recomendada × 100`. `null` si no hay contexto o si la solución viene de un `RoutingConfig` anterior al sweep rankeado (no comparable). |
| `technical_tie` | `true` si el travel está dentro del 3 % de **la recomendada** y no es la recomendada misma. Medirlo contra el control haría que el control se marque siempre como empatado consigo mismo. |
| `balance_below_gate` | `true` si `balance_score < BALANCE_GATE (0.60)`. |
