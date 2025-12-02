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

# Opción 2: Abrir directamente (si el navegador lo permite)
open viewer/index.html
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
