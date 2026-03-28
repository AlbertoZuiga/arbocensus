# Visualizador - Guia Rapida

## 1) Generar GeoJSON

Despues de ejecutar el pipeline (o al menos `graph`, `route` y `export`), genera las capas:

```bash
python run.py export
```

Se escriben en `artifacts/runs/latest/output/`:

- `bbox.geojson`
- `input_points.geojson`
- `filtered_points.geojson`
- `clusters.geojson`
- `cluster_polygons.geojson`
- `routes.geojson`

## 2) Abrir el viewer

```bash
python -m http.server 8000
```

URLs:

- `http://localhost:8000/viewer/index.html`

## Viewer

Incluye:

- carga de capas desde `artifacts/runs/latest/output/`
- lectura de metricas de rutas desde `artifacts/runs/latest/route/routes.json`
- popups con `travel_seconds`, `service_seconds`, `total_seconds`, `validated_by`

## Controles

- checkboxes para activar/desactivar capas
- botones de etapas para presets de visualizacion
- click y hover sobre rutas para inspeccion

## Troubleshooting

Problema: el mapa aparece vacio.

- Ejecuta `python run.py export` para regenerar capas.
- Verifica que existan archivos en `artifacts/runs/latest/output/`.

Problema: errores 404 al cargar GeoJSON.

- Sirve el proyecto con `python -m http.server 8000`.
- Abre el viewer por `http://localhost:8000/...` en lugar de `file://`.
