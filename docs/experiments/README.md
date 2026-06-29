# Registro de experimentos

Cada ejecución del pipeline de optimización que produce un resultado analizable
escribe aquí un informe Markdown con marca de tiempo
(`AAAAMMDD-HHMMSS-<slug>.md`). El objetivo es acumular material reutilizable para
la redacción de la tesis.

## Quién escribe aquí

- `manage.py seed_demo` (cuando corre la optimización) → `*-seed-demo.md`.
- `manage.py baseline_sweep` → `*-baseline-sweep.md`. Acepta
  `--strategy {global,spatial_term,cluster_first}` (por defecto `global`) para
  barrer cada estrategia de partición espacial; el informe registra la estrategia
  usada en su cabecera y parámetros.

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
