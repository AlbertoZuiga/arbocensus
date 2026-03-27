# 🗺 Visualizador - Guía Rápida

## Generar GeoJSON para el Viewer

Después de ejecutar el pipeline completo, debes generar los archivos GeoJSON:

```bash
python run.py export
```

Esto genera en `artifacts/runs/latest/06_output/`:

- `bbox.geojson` - Límites del área
- `input_points.geojson` - Árboles originales
- `filtered_points.geojson` - Árboles filtrados
- `clusters.geojson` - Nodos por cluster
- `cluster_polygons.geojson` - Polígonos de clusters
- `routes.geojson` - Rutas TSP

## Abrir el Viewer

```bash
# Opción 1: Servidor HTTP simple
python -m http.server 8000

# Luego abrir en navegador:
# http://localhost:8000/viewer/index.html
# http://localhost:8000/viewer/index_v3.html

# Opción 2: Abrir directamente (si el navegador lo permite)
open viewer/index.html
open viewer/index_v3.html

## Viewer V3

`viewer/index_v3.html` es una copia del viewer base adaptada para el pipeline `--v3`.

Incluye:

- fallback de rutas de salida (`output` y `06_output`)
- lectura de métricas de routing desde `artifacts/runs/latest/route/routes.json`
- popups enriquecidos con `travel_seconds`, `service_seconds`, `total_seconds` y `validated_by`
- panel de resumen con métricas agregadas por ruta
```

## Controles del Viewer

- **Checkboxes**: Activar/desactivar capas
- **Botones Stage 1-5**: Presets de visualización por etapa
- **Click en rutas**: Ver detalles del cluster
- **Hover en rutas**: Resaltar ruta

## Troubleshooting

**Problema:** El viewer está vacío

**Solución:** Ejecutar `python run.py export` para regenerar GeoJSON

**Problema:** Error 404 al cargar archivos

**Solución:** Servir con HTTP server (no abrir directamente el archivo HTML)
