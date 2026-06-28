# Baseline geográfico VRP global · uniform

- Fecha (UTC): 2026-06-27T22:12:00
- Comando: `manage.py baseline_sweep`
- Parámetros:
- `sizes`: 20,40,80
- `seeds`: 5
- `distribution`: uniform
- `solver_time_limit_sec`: 180

## Métricas

| Métrica | Valor |
| --- | --- |
| semillas | 5 |
| tamaños | 20,40,80 |

## Qué ocurrió

Media por tamaño de dataset sobre el barrido:

| n | k | balance | sum_rmax [m] | solap. total | solap./ruta | IoU peor par |
| --- | --- | --- | --- | --- | --- | --- |
| 20 | 3.0 | 0.946 | 6530 | 0.4 | 0.13 | 0.01 |
| 40 | 5.0 | 0.949 | 8758 | 6.6 | 1.32 | 0.13 |
| 80 | 8.0 | 0.872 | 13126 | 25.8 | 3.23 | 0.28 |

El balance temporal se mantiene alto (0.87–0.95) mientras el solapamiento entre
rutas crece de forma monótona con la densidad, tanto absoluto (0.4 → 6.6 → 25.8)
como normalizado por ruta (0.13 → 1.32 → 3.23). El IoU del peor par sigue la
misma tendencia (0.01 → 0.13 → 0.28).

## Por qué ocurrió

El modelo resuelve un único Open mTSP global que minimiza el tiempo total con una
penalización blanda de balance temporal, sin ningún criterio espacial explícito
en la partición de nodos. Las rutas se forman por proximidad temporal, no
geográfica.

## Posibles causas

- Ausencia de término espacial en la función objetivo.
- El balance blando premia rutas de duración similar aunque se entrelacen geográficamente.
- Mayor densidad de nodos aumenta la probabilidad de que una ruta compacta quede contenida en la caja de otra más extensa.

## Hipótesis

- H1: un preprocesamiento de clustering geográfico (resolver un VRP por cluster) reduce el solapamiento por ruta sin degradar el balance temporal.
- H2: el solapamiento crece de forma monótona con la densidad de nodos independientemente de la semilla.
- H3: añadir un término de compacidad espacial al objetivo reduce el IoU del peor par a costa de mayor tiempo total.

## Cómo validar cada hipótesis

- H1: correr `baseline_sweep --distribution clustered` y comparar interleave_per_route contra uniform a igual n.
- H2: inspeccionar la dispersión por semilla (no solo la media) en cada tamaño.
- H3: implementar el término espacial y re-medir sum_max_radius, interleave y balance.

## Posibles soluciones o enfoques alternativos

- Clustering geográfico como preprocesamiento (k-means / DBSCAN) y un VRP por cluster.
- Penalización de compacidad espacial en el objetivo del solver.
- Restricciones de zona (capacidad por sector) en OR-Tools.

## Métricas o experimentos recomendados para confirmar

- Comparar uniform vs clustered vs multizone con baseline_sweep.
- Medir el trade-off tiempo-total vs solapamiento al variar el peso del término espacial.
