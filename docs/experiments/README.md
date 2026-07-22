# Registro de experimentos

Cada ejecución del pipeline de optimización que produce un resultado analizable
escribe aquí un informe Markdown. Los informes se archivan con el nombre
`<slug>-AAAAMMDD.md`. El objetivo es acumular material reutilizable para
la redacción de la tesis.

## Quién escribe aquí

- `manage.py seed_demo` (cuando corre la optimización) → `*-seed-demo.md`.
- `manage.py baseline_sweep` → `*-baseline-sweep.md` + `*-baseline-sweep.csv`
  (una fila por corrida, con métricas de rutas y timing por fase). Acepta
  `--dataset <uuid>` para barrer un dataset real (sin `--dataset` genera datasets
  sintéticos según `--sizes`/`--distribution`), `--strategies` (lista separada
  por comas: `global,spatial_term,cluster_first`), `--service-time <min,...>` y
  `--t-max <h,...>` (producto cartesiano de variantes de duración),
  `--time-limit <s>` (fija el límite del solver en vez de la heurística del
  pipeline) y `--csv <ruta>`. Sobre un dataset real la semilla solo etiqueta la
  repetición: la varianza proviene del corte por tiempo del solver.
- `manage.py route_audit` → `*-route-audit.md` + CSV por ruta (`--csv <ruta>`) +
  GeoJSON (`--geojson <ruta>`). Radiografía de UNA corrida del pipeline sobre un
  dataset real (`--dataset <uuid>`, `--strategy`, `--service-time <s>`, `--t-min <s>`,
  `--t-max <s>`, `--time-limit <s>`, `--seed`): walk_ratio, servicio, caminata,
  shortfall contra T_min, saturación contra T_max y auto-cruces de la secuencia de
  paradas, por ruta y en una fila `summary`. El GeoJSON trae un LineString por ruta y
  un Point por parada, para inspección visual (geojson.io / QGIS). Con
  `--worst-pair-geojson <ruta>` emite además el peor par de rutas por IoU de bbox.
- `manage.py greedy_baseline` → `*-greedy-baseline.md` + CSV con `--csv <ruta>`.
  Baseline de vecino más cercano sobre un dataset real (`--dataset <uuid>`,
  `--service-time <min>`, `--t-max <h>`), con las mismas métricas de calidad de
  rutas que `baseline_sweep` para que ambas corridas sean comparables. Es
  determinista: una sola fila, sin semillas.
- `manage.py config_algorithm_sweep` → CSV con `--csv <ruta>` (una fila por celda).
  Barre configuración × algoritmo × tamaño sobre la suite de instancias congeladas
  (config censal: servicio 2 min, T_max 3 h). Reanudable (salta celdas ya presentes)
  y `--only-instance` / `--only-cell` / `--seeds` para acotar. Las celdas OR-Tools
  corren dentro de una transacción revertida para no ensuciar la base compartida.
  Los overrides de configuración que barre existen como flags en `route_audit`
  (`--balance-arm`, `--span-cost-coefficient`); son opt-in y no alteran el default.
  `--seeds` son réplicas reales desde `sweep-metrology-20260720`: la semilla permuta
  el orden de los nodos antes de construir el modelo (OR-Tools no expone semilla de
  RNG), así que mide la varianza del pipeline entero. La semilla 0 es la identidad.
  Las celdas `greedy` son deterministas y corren una sola vez por instancia.
  `--starts <N>` resuelve cada celda con N órdenes de nodos distintos y conserva el
  mejor por objetivo del solver; `--budget per-start|total` elige si cada arranque
  recibe el límite de tiempo completo o si uno solo se reparte entre los N. Con
  `--starts 1` (default) el camino de código es el de siempre.
- `manage.py instance_decomposition` → CSV con `--csv <ruta>`. Aritmética estructural
  pura (sin solver) de una o varias instancias (`--instance <slug> ...`): para cada `k`
  la cota inferior `MSF_k` (bosque generador mínimo de `k` componentes), la cota vieja
  de vecino más cercano y el techo por `T_max`.
- `manage.py rejudge_relleno` → CSV con `--out <ruta>`. Recomputa la métrica de relleno
  de barridos ya publicados (`--sweep <csv> ...`) contra `MSF_k` (`--decomposition <csv>`),
  sin solver ni OSRM. Las filas con `drops > 0` quedan vacías: la cota no las acota.

Las instancias reales sobre las que corren estos comandos viven congeladas en
[`instances/`](instances/README.md) (`manage.py freeze_legacy` las vuelca desde la
base legacy; `manage.py load_instances` las carga con UUID deterministas).

La carpeta se resuelve desde `settings.EXPERIMENTS_DIR`
(`docs/experiments/` por defecto; configurable con la variable de entorno
`EXPERIMENTS_DIR`). En Docker se monta `./docs:/docs`, por lo que los informes
generados dentro del contenedor quedan visibles en el host.

## Estructura de cada informe

Cabecera con fecha, comando y parámetros, una tabla de **métricas** reales y, a
continuación, secciones de análisis:

- **Qué ocurrió** — se autocompleta con el resumen de la corrida.
- **Por qué ocurrió · Posibles causas · Hipótesis · Cómo validar cada hipótesis ·
  Posibles soluciones · Métricas o experimentos recomendados** — el comando
  precarga lo que ya se sabe (p. ej. el hallazgo del baseline); el resto queda
  como `Pendiente de completar` para rellenar tras analizar la corrida.

Las métricas y el "qué ocurrió" son datos reales medidos; las secciones
analíticas son interpretación humana y no deben fabricarse.
