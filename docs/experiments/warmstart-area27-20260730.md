# Warm start greedy en area-27

**Objetivo:** decidir si el defecto de `area-27-n72` (#261: OR-Tools abre 2 rutas donde el greedy
cabe en 1, +57 % travel) es un fallo de **búsqueda** o un término del modelo no capturado por
`vehicle_bounds`.

**Método:** inyectar la solución greedy (k=1) como warm start (`--only-cell warm-greedy`,
`ReadAssignmentFromRoutes`) y ver si el solver la conserva. Control `--only-cell actual` en el mismo
CSV (cold start). 3 semillas, `--post-resequence`.

## Resultado

| cell | seed | k | travel_sec | crossings_road | drops |
| --- | --- | --- | --- | --- | --- |
| warm-greedy | 1/2/3 | **2** | 2420/2332/2420 | 4/2/4 | 0 |
| actual (control) | 1/2/3 | **2** | 2790/2390/2302 | 5/3/4 | 0 |

3/3 semillas del warm start **abandonan** la ruta única de 1 vehículo y convergen a k=2, igual que el
control frío. Verificado además con `node_seed=0` (permutación identidad) — mismo resultado, descarta
un bug en la inversión de permutación del warm start (`solver.py:326-330`).

## Instrumentación directa del objetivo (no queda en el código, solo en este informe)

Con `node_seed=0`, greedy directo (`solve_greedy`) da k=1, 72 nodos, duración 10 694 s (cabe bajo
`T_max`=10 800 s, no lo particiona `split_to_solver_capacity`). Se leyó `assignment.ObjectiveValue()`
del warm start antes de resolver y `solution.ObjectiveValue()` al final, más los cumuls de la
dimensión Time al término de cada vehículo:

```
warm start (k=1, un solo vehículo): objective = 964 903
solución final (k=2):               objective = 229 709
time_end_cumuls: [7200, 7200, 0, 0, ...]   ← ambas rutas terminan EXACTO en T_min
```

**El objetivo del propio solver prefiere la partición en 2 por ~4,2×.** No es fallo de búsqueda: GLS
encontró y devolvió correctamente el óptimo local más barato bajo el precio vigente.

## Reconciliación con el diagnóstico de #261

Ese diagnóstico afirmaba lo contrario — que el objetivo prefiere la ruta única por ~43× (704 500 vs 30 570 000) y
que el solver la abandona pese a eso, localizando el defecto en la búsqueda. Esa aritmética asumía que
las 2 rutas quedaban **por encima** del target superior (usando 5 766/5 597 s como si fueran overshoot
de `T_max`/target). La instrumentación de esta sesión muestra el mecanismo real: ambas rutas del
split terminan **exactamente en el piso `T_min`=7 200 s** — la dimensión Time del solver, no
`total_estimated_time_sec` (que reporta 5 299/5 819 s, la duración "real" sin relleno). La diferencia
entre ambos números es relleno: el solver detourea gratis porque el precio marginal por debajo de
`T_min` es −9 999/s (`.claude/rules/ortools-vrp.md`, tabla de precio marginal).

**Esto es el régimen de relleno por `T_min` ya documentado**: cuando `k·T_min` excede el
trabajo real, el solver rellena. Aquí `2×7200=14400 s` ≫ `10 694 s` de trabajo real de la ruta única,
así que partir y rellenar sale más barato (200 000 de costo fijo + relleno gratis) que una sola ruta
que se pasa del target superior (100 000 + `(10 694−9 000)×500=847 000`).

**Veredicto: #261 diagnosticó mal el mecanismo.** No es un hueco de búsqueda nuevo — es el relleno
por `T_min` manifestándose en una instancia de baja densidad donde el trabajo real de una
sola ruta cabe bajo `T_max` pero muy por debajo de `2×T_min`. La palanca ya se intentó (piso de
paradas, `stops-floor-sweep-20260720.md`; piso combinado, `combined-floor-sweep-20260720.md`) y
está cerrada sin cambio de default.

**No hay palanca nueva aquí.** El post-pass de fusión de rutas propuesto como alternativa no está
justificado: fusionar exigiría deshacer exactamente el relleno que resulta ser el mecanismo, y esa familia de intervenciones (pisos, combinados) ya fue medida y descartada.

## Acción

- Sección de áreas reales de la tesis: el caso se reclasifica de "fallo de búsqueda" a régimen de
  relleno por `T_min` en instancia de baja densidad; no se abre ningún ciclo nuevo de precios.
- Sin cambio de código de producción.
