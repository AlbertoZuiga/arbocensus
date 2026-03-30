# 🌳 Arbocensus: Generador de Rutas Óptimas para Censo de Árboles

Pipeline para generar rutas de censo de arboles y exportar capas GeoJSON para visualizacion.

- [🌳 Arbocensus: Generador de Rutas Óptimas para Censo de Árboles](#-arbocensus-generador-de-rutas-óptimas-para-censo-de-árboles)
  - [Estado actual](#estado-actual)
  - [Estructura relevante](#estructura-relevante)
  - [Requisitos](#requisitos)
    - [Formateo y Hooks Locales](#formateo-y-hooks-locales)
    - [Configuración de Base de Datos (Opcional)](#configuración-de-base-de-datos-opcional)
  - [CLI](#cli)
  - [Uso rapido](#uso-rapido)
  - [Artefactos por defecto](#artefactos-por-defecto)
  - [Viewer](#viewer)
  - [Desarrollo](#desarrollo)
  - [Modulos legacy](#modulos-legacy)
  - [Documentacion adicional](#documentacion-adicional)
  - [Soporte](#soporte)


## Estado actual

- El flujo principal es: input -> filter -> graph -> route -> export.
- `route/routes.json` es la fuente para la asignacion de clusters en export.

## Estructura relevante

- `run.py`: entrypoint del CLI.
- `src/arbocensus_pipeline/cli.py`: comandos del pipeline.
- `src/arbocensus_pipeline/input.py`: carga de datos desde bbox o DB.
- `src/arbocensus_pipeline/filter.py`: limpieza y filtrado.
- `src/arbocensus_pipeline/graph.py`: grafo sparse via KD-tree.
- `src/arbocensus_pipeline/optimize.py`: optimizacion de rutas.
- `src/arbocensus_pipeline/routing.py`: tiempos de viaje y cache.
- `src/arbocensus_pipeline/export.py`: exportacion GeoJSON.
- `viewer/index_v3.html`: viewer recomendado.

## Requisitos

- Python 3.12
- Entorno virtual (`venv`)

Instalacion:

```bash
# Clonar repositorio
git clone https://github.com/AlbertoZuiga/arbocensus
cd arbocensus

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias del pipeline
pip install -r requirements.txt
pip install -r requirements-linters.txt

# Instalar hooks de git (Husky + Commitlint)
npm install

# Convertir run.py en ejecutable (opcional: en caso de no realizar los comandos deberan realizarse con python run.py en lugar de ./run.py)
chmod 744 run.py
```

### Formateo y Hooks Locales

Se agrega una capa de validación automática para mantener estilo y mensajes de commit consistentes:

- `black` e `isort` para formateo y orden de imports en Python
- `pre-commit` ejecutado desde `.husky/pre-commit`
- `commitlint` ejecutado desde `.husky/commit-msg`
- workflow de GitHub Actions que valida formato en cada Pull Request hacia `main`

### Configuración de Base de Datos (Opcional)

Si quieres cargar árboles directamente desde PostgreSQL:

Crea archivo `.env` en la raíz:

```bash
ARBOCENSUS_DB_URL=postgres://user:pass@host:5432/db_name
ARBOCENSUS_API_DB_URL=postgres://user:pass@host:5432/api_db
```

El pipeline intentará conectarse usando estas credenciales. Si fallan, usará el archivo `saved_bbox.json` como fallback.

---

## Web Application (Django)

The backend is a Django application that exposes a REST API backed by PostgreSQL.

### Running with Docker Compose

```bash
# Copy and configure environment variables
cp .env.example .env
# Edit .env to set a strong SECRET_KEY

# Start all services (database + Django + OSRM)
docker compose up
```

The API will be available at `http://localhost:8000/`.

### Apply Migrations

```bash
docker compose exec web python manage.py migrate
```

### Create a Superuser

```bash
docker compose exec web python manage.py createsuperuser
```

Access the Django admin at `http://localhost:8000/admin/`.

### Backend Structure

```
backend/
├── manage.py
├── Dockerfile
├── requirements.txt
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   └── development.py   # Development overrides
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── apps/
    └── api/                 # Main API app (models, views, admin)
```

---

## CLI

Ayuda general:

```bash
python run.py --help
```

Subcomandos disponibles:

- `input`
- `filter`
- `graph`
- `route`
- `export`

Flags globales:

- `--run-id`: identifica un run.
- `--outdir`: directorio base de runs.

## Uso rapido

Pipeline completo:

```bash
python run.py
```

Pipeline por etapas:

```bash
python run.py input --bbox bbox/saved_bbox.json
python run.py filter
python run.py graph
python run.py route
python run.py export
```

## Artefactos por defecto

Por default los outputs van a `artifacts/runs/latest/`:

- `bbox_input/input.json`
- `filter/filtered.json`
- `graph/graph.json`
- `route/routes.json`
- `output/bbox.geojson`
- `output/input_points.geojson`
- `output/filtered_points.geojson`
- `output/clusters.geojson`
- `output/cluster_polygons.geojson`
- `output/routes.geojson`

## Viewer

Generar capas y servir archivos:

```bash
python run.py export
python -m http.server 8000
```

Abrir en navegador:

- `http://localhost:8000/viewer/index.html`

## Desarrollo

Comandos de formato y chequeo:

```bash
black .
isort .
black --check .
isort --check-only .
./venv/bin/python -m pre_commit run --all-files
```

## Modulos legacy

- `tsp.py` permanece en el repositorio por compatibilidad historica, pero no participa del flujo CLI actual.
- El flujo activo usa `optimize.py` + `routing.py`.

## Documentacion adicional

- `docs/VIEWER_QUICKSTART.md`
- `docs/pseudo-codigo.md`
- `docs/TODO.md`

## Soporte

- Issues: [GitHub Issues](https://github.com/AlbertoZuiga/arbocensus/issues)
