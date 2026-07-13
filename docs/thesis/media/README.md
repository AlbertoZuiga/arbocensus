# Figuras de mapa de §3.1.4

Las tres figuras `fig-*.pdf` / `fig-*.png` de este directorio se generan **offline** desde los
artefactos de la auditoría de rutas ya versionados (PR #154,
`docs/experiments/route-audit-20260713-*`) con `scripts/route_figures.py`. No requieren Docker, ni
el solver, ni OSRM, ni base de datos: el script solo lee el GeoJSON y el CSV de cada corrida.

Toda cifra que aparece en una figura (duración, walk_ratio, número de cruces, totales) sale del
CSV de la auditoría. Los cruces dibujados con `×` se recalculan con la misma geometría que
`backend/apps/optimization/route_audit.py` y el script **falla** si el conteo no coincide con la
columna `self_crossings` del CSV.

## Preparación (una vez)

```bash
python -m venv .venv-figures
.venv-figures/bin/pip install -r scripts/requirements-figures.txt
```

Los comandos siguientes se corren desde la raíz del repo con `.venv-figures/bin/python`.

## Figuras

### `fig-ruta-vueltas-r1` — una ruta con vueltas y su contexto

Ruta 19 de R1 (caso real n=1607, `spatial_term`): la ruta con más auto-cruces de la referencia
(13) pese a tener el walk_ratio más bajo de su corrida (13,1 %). Panel izquierdo: su vecindario,
con las rutas contiguas en gris. Panel derecho: la ruta aislada, con sus 13 cruces marcados.

```bash
.venv-figures/bin/python scripts/route_figures.py single \
  --geojson docs/experiments/route-audit-20260713-r1.geojson \
  --csv docs/experiments/route-audit-20260713-r1.csv \
  --highlight 19 --zoom-route 19 --crop-to-highlight --context-pad 2.0 \
  --label "Vecindario de la ruta 19 (gris: rutas contiguas)" \
  --title "Caso real (n=1607, spatial_term): la ruta 19 y su contexto" \
  --out docs/thesis/media/fig-ruta-vueltas-r1
```

### `fig-peor-par` — entrelazado inter-ruta

Peor par por IoU de bbox en cada estrategia: `spatial_term` (rutas 4 y 15, IoU 0,30) frente a
`global` (rutas 4 y 8, IoU 0,58). Los IoU salen de la tabla §d de
`docs/experiments/route-audit-20260713.md`; el resto de las cifras, de los CSV por ruta.

```bash
.venv-figures/bin/python scripts/route_figures.py compare \
  --left-geojson docs/experiments/route-audit-20260713-r4-worst-pair.geojson \
  --left-csv docs/experiments/route-audit-20260713-r1.csv \
  --left-label "spatial_term: rutas 4 y 15 (IoU de bbox 0,30)" \
  --right-geojson docs/experiments/route-audit-20260713-r2-worst-pair.geojson \
  --right-csv docs/experiments/route-audit-20260713-r2.csv \
  --right-label "global: rutas 4 y 8 (IoU de bbox 0,58)" \
  --title "Peor par de rutas por solapamiento de bbox (caso real, n=1607)" \
  --out docs/thesis/media/fig-peor-par
```

### `fig-regimen-disperso-vs-real` — contraste de régimen

Disperso sintético n=40 (walk_ratio agregado 67,0 %, caminata legítima entre árboles lejanos)
frente al caso real n=1607 (walk_ratio 23,3 %, geometría enredada). Es la figura que muestra que
el walk_ratio alto **no** es la queja visual.

El panel derecho se encuadra en las rutas 2–25: la ruta 1 alcanza un árbol periférico y su tramo
sale del recuadro (se ve cruzando el borde inferior izquierdo). Sin ese encuadre, esa sola ruta
comprime al resto en una mancha ilegible.

```bash
.venv-figures/bin/python scripts/route_figures.py compare \
  --left-geojson docs/experiments/route-audit-20260713-r3b.geojson \
  --left-csv docs/experiments/route-audit-20260713-r3b.csv \
  --left-label "Disperso sintético n=40 (caminata agregada 67,0 %)" \
  --right-geojson docs/experiments/route-audit-20260713-r1.geojson \
  --right-csv docs/experiments/route-audit-20260713-r1.csv \
  --right-label "Caso real n=1607 (caminata agregada 23,3 %)" \
  --right-focus 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 \
  --right-pad 0.08 \
  --title "Régimen de caminata: el walk_ratio alto no es la queja visual" \
  --out docs/thesis/media/fig-regimen-disperso-vs-real
```

## Uso en LaTeX

Los `.pdf` son vectoriales y son el formato a incluir (los `.png` existen para revisión rápida en
GitHub). Desde `docs/thesis/`:

```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=\textwidth]{media/fig-peor-par.pdf}
  \caption{...}
  \label{fig:peor-par}
\end{figure}
```

## Notas de diseño

- Impresión en blanco y negro: cada ruta se distingue por color **y** por estilo de línea **y**
  por marcador; la paleta (Okabe-Ito) tiene luminancias separadas en escala de grises.
- Sin basemap: la reproducción es offline y determinista (el PDF se re-renderiza byte a byte
  idéntico, así que regenerar no ensucia el diff).
- Proyección equirectangular local en metros, la misma de `strategies.project_equirectangular`;
  cada panel lleva escala gráfica y flecha de norte, sin ejes de lat/lon.
- Cuando un panel muestra más rutas que `--legend-max` (6 por defecto), la leyenda pasa a la fila
  `resumen` del CSV en vez de listar 25 entradas ilegibles.
