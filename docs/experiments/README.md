# Registro de experimentos

Cada ejecución del pipeline de optimización que produce un resultado analizable
escribe aquí un informe Markdown con marca de tiempo
(`AAAAMMDD-HHMMSS-<slug>.md`). El objetivo es acumular material reutilizable para
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
- `manage.py greedy_baseline` → `*-greedy-baseline.md` + CSV con `--csv <ruta>`.
  Baseline de vecino más cercano sobre un dataset real (`--dataset <uuid>`,
  `--service-time <min>`, `--t-max <h>`), con las mismas métricas de calidad de
  rutas que `baseline_sweep` para que ambas corridas sean comparables. Es
  determinista: una sola fila, sin semillas.

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
