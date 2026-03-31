# 🌳 Arbocensus: Generador de Rutas Óptimas para Censo de Árboles

Pipeline para generar rutas de censo de arboles y exportar capas GeoJSON para visualizacion.

- [🌳 Arbocensus: Generador de Rutas Óptimas para Censo de Árboles](#-arbocensus-generador-de-rutas-óptimas-para-censo-de-árboles)
  - [Estado actual](#estado-actual)
  - [Estructura relevante](#estructura-relevante)
  - [Requisitos](#requisitos)
    - [Formateo y Hooks Locales](#formateo-y-hooks-locales)
    - [Configuración de Base de Datos (Opcional)](#configuración-de-base-de-datos-opcional)
  - [Web Application (Django)](#web-application-django)
  - [API](#api)
  - [Viewer](#viewer)
  - [Desarrollo](#desarrollo)
  - [Modulos legacy](#modulos-legacy)
  - [Documentacion adicional](#documentacion-adicional)
  - [Soporte](#soporte)


## Estado actual

- El flujo principal es: input -> filter -> graph -> route -> export.
- El pipeline se ejecuta a través de la API REST del backend Django.

## Estructura relevante

- `src/arbocensus_pipeline/input.py`: carga de datos desde bbox o DB.
- `src/arbocensus_pipeline/filter.py`: limpieza y filtrado.
- `src/arbocensus_pipeline/graph.py`: grafo sparse via KD-tree.
- `src/arbocensus_pipeline/optimize.py`: optimizacion de rutas.
- `src/arbocensus_pipeline/routing.py`: tiempos de viaje y cache.
- `src/arbocensus_pipeline/export.py`: exportacion GeoJSON.
- `backend/apps/api/services/pipeline.py`: orquestación del pipeline.
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

The backend is a Django application that exposes a REST API backed by PostgreSQL. The pipeline is now triggered via the API — the CLI entry point has been replaced by the web API.

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
    └── api/                 # Main API app (models, views, admin, services)
        ├── models.py        # Includes PipelineRun model
        ├── views.py
        ├── admin.py
        ├── urls.py
        └── services/
            └── pipeline.py  # Pipeline orchestration service
```

---

## API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/` | API root — lists available endpoints |
| GET | `/api/health/` | Health check |
| GET | `/api/runs/` | List all pipeline runs |
| POST | `/api/runs/` | Create and start a new pipeline run |
| GET | `/api/runs/{id}/` | Get run status and summary |
| GET | `/api/runs/{id}/routes.geojson` | Get routes GeoJSON (completed runs only) |
| GET | `/api/runs/{id}/clusters.geojson` | Get clusters GeoJSON (completed runs only) |

### Starting a Pipeline Run

```bash
curl -X POST http://localhost:8000/api/runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "north": -33.40,
    "south": -33.45,
    "east": -70.60,
    "west": -70.65,
    "expected_duration_min": 150.0,
    "time_per_tree_min": 2.0
  }'
```

### Retrieving Results

```bash
# Get run status
curl http://localhost:8000/api/runs/1/

# Get routes GeoJSON (once completed)
curl http://localhost:8000/api/runs/1/routes.geojson

# Get clusters GeoJSON (once completed)
curl http://localhost:8000/api/runs/1/clusters.geojson
```

## Viewer

Fetch routes GeoJSON from the API and serve the viewer:

```bash
python -m http.server 8001
```

Abrir en navegador:

- `http://localhost:8001/viewer/index.html`

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

- `tsp.py` permanece en el repositorio por compatibilidad historica, pero no participa del flujo activo.
- El flujo activo usa `optimize.py` + `routing.py`, orquestados por `backend/apps/api/services/pipeline.py`.

## Documentacion adicional

- `docs/VIEWER_QUICKSTART.md`
- `docs/pseudo-codigo.md`
- `docs/TODO.md`

## Soporte

- Issues: [GitHub Issues](https://github.com/AlbertoZuiga/arbocensus/issues)
