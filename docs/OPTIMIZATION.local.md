# Optimización de rutas — referencia técnica

## §1 Estrategias

El solver soporta tres estrategias (`RoutingSolution.Strategy`):

| Valor | Descripción |
|---|---|
| `global` | VRP puro, minimiza caminata total. |
| `spatial_term` | VRP + penalización de span geográfico (por defecto `SPATIAL_SPAN_COEF=3`). Reduce entrecruzamiento de rutas. |
| `cluster_first` | k-means → VRP por cluster. Refutada experimentalmente; disponible solo para sweeps de investigación mediante argumento explícito `strategy=cluster_first`. |

La **estrategia por defecto de producción es `spatial_term`** (no `global`). El pipeline corre `global` y `spatial_term` en paralelo y el criterio de recomendación elige al ganador.

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

Un POST a `/api/optimization/jobs/` crea **4 jobs** con estrategia explícita:

| preset | strategy |
|---|---|
| `default` | `global` |
| `default` | `spatial_term` |
| `temporal_span_100` | `spatial_term` |
| `arc_linear_30` | `spatial_term` |

Cada job corre una sola estrategia (`pipeline.run(strategy=...)`).

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

Si el viaje de la primera candidata según el orden estricto difiere menos de **3 %** del viaje de la solución control (`default×spatial_term`), gana el control. Esto evita que un desempate arbitrario por `id` cambie la recomendación entre sweeps cuando dos soluciones son prácticamente equivalentes.

### Supuesto de nómina

El criterio minimiza `total_travel_time_sec` asumiendo que **los censistas se pagan por hora**: menos caminata = menor costo total. Si el pago fuera por jornada/turno, el costo real relevante sería `k = total_routes`, que hoy participa solo como desempate secundario (paso 5 del orden).

## §7 Campos del serializer relacionados

| Campo | Descripción |
|---|---|
| `recommended` | `true` si es la solución recomendada del dataset (según criterio + regla de empate). |
| `travel_margin_pct` | `(travel_propio − travel_recomendada) / travel_recomendada × 100`. `null` si no hay contexto. |
| `technical_tie` | `true` si el travel del candidato está dentro del 3 % del control (`default×spatial_term`). |
| `balance_below_gate` | `true` si `balance_score < BALANCE_GATE (0.60)`. |
