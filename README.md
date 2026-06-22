# Arbocensus: Optimización de Rutas para Censo de Árboles Urbanos

Proyecto de Titulo - Ingeniería Civil en Ciencias de la Computación

- [Arbocensus: Optimización de Rutas para Censo de Árboles Urbanos](#arbocensus-optimización-de-rutas-para-censo-de-árboles-urbanos)
  - [Desarrollo Rápido](#desarrollo-rápido)
    - [Con Docker (recomendado)](#con-docker-recomendado)
    - [Desarrollo Local](#desarrollo-local)
    - [Comandos Comunes](#comandos-comunes)
    - [Estructura del Proyecto](#estructura-del-proyecto)
    - [Stack Técnico](#stack-técnico)
  - [Problema de Investigación](#problema-de-investigación)
  - [Contexto](#contexto)
  - [Enfoque de Solución](#enfoque-de-solución)

---

## Desarrollo Rápido

### Con Docker (recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/AlbertoZuiga/arbocensus.git
cd arbocensus

# 2. Configurar variables de entorno
cp .env.example .env

# 3. Descargar datos OSM para OSRM (primera vez, ~800 MB)
mkdir -p data/osm
curl -L https://download.geofabrik.de/south-america/chile-latest.osm.pbf \
     -o data/osm/chile-latest.osm.pbf

# 4. Levantar servicios
docker compose up
```

OSRM procesa el PBF en el primer inicio (~10–15 min). Posterior a eso levanta en segundos.

Servicios disponibles:

| Servicio   | URL                                            |
| ---------- | ---------------------------------------------- |
| API Django | [http://localhost:8000](http://localhost:8000) |
| PostgreSQL | localhost:5432                                 |
| Redis      | localhost:6379                                 |
| OSRM       | [http://localhost:5000](http://localhost:5000) |

### Desarrollo Local

```bash
# 1. Instalar dependencias (Python + Node + hooks de git)
./scripts/setup.sh
source .venv/bin/activate

# 2. Levantar solo la base de datos y Redis con Docker
docker compose up db redis

# 3. Aplicar migraciones y levantar el servidor
cd backend
python manage.py migrate
python manage.py runserver
```

El script crea el `.venv`, instala `backend/dev-requirements.txt` (prod + dev) y ejecuta `npm install` (que configura Husky automáticamente).

Para agregar o actualizar dependencias Python, editar el `.in` correspondiente en `backend/` y recompilar:

```bash
cd backend
pip-compile requirements.in -o requirements.txt
pip-compile dev-requirements.in -o dev-requirements.txt
```

### Comandos Comunes

```bash
# Linting
npm run lint              # Ejecutar todos los linters
npm run lint:py           # Linting Python (ruff)
npm run lint:js           # Linting JavaScript/Markdown

# Formateo
npm run format            # Formatear código Python
npm run format:check      # Verificar formato sin cambiar

# Type checking
npm run type-check        # Verificar tipos con pyright

# Testing (dentro del contenedor backend — requiere GDAL + PostGIS)
make -C backend test                      # Todos los tests
make -C backend test ARGS="apps/optimization/tests"  # Subconjunto

# Django (desde backend/)
python manage.py migrate
python manage.py createsuperuser
celery -A config worker --loglevel=info
```

> Los tests corren **dentro del contenedor backend**, no en el host. Los modelos
> geográficos (`PointField`) requieren GDAL y una base PostGIS, ambos provistos por
> la imagen `dev` y el servicio `db`. `make -C backend test` construye el target
> `dev` (con las dependencias de testing) y ejecuta pytest contra `db`.

### Estructura del Proyecto

```bash
.
├── backend/                  # Django + PostGIS API
│   ├── apps/
│   │   ├── accounts/         # Auth, CustomUser, roles
│   │   ├── datasets/         # Importación y gestión de árboles
│   │   ├── optimization/     # OR-Tools VRP solver, Celery jobs
│   │   └── routes/           # Soluciones y RouteStops
│   ├── config/               # Django settings, URLs, Celery
│   ├── Dockerfile
│   └── requirements.txt
├── data/osm/                 # PBF para OSRM (ignorado en git)
├── docs/                     # Documentación y tesis
├── scripts/                  # Scripts de setup y utilidades
├── tools/
│   └── scripts/              # Scripts de lint, format, test
├── .github/                  # Workflows CI/CD
├── .husky/                   # Git hooks
├── docker-compose.yml
├── pyproject.toml            # Ruff, pytest, pyright, coverage
└── package.json              # Commitlint, Husky, scripts npm
```

### Stack Técnico

**Backend (en desarrollo):**

- [Django 4.2](https://docs.djangoproject.com/) + [GeoDjango](https://docs.djangoproject.com/en/4.2/ref/contrib/gis/) — API REST con soporte geoespacial
- [PostGIS 3.3](https://postgis.net/) sobre PostgreSQL 15 — almacenamiento de geometrías
- [OR-Tools](https://developers.google.com/optimization) — solver VRP para optimización de rutas
- [Celery](https://docs.celeryq.dev/) + [Redis 7](https://redis.io/) — ejecución asíncrona de jobs de optimización
- [OSRM](http://project-osrm.org/) — matriz de costos de routing peatonal

**Frontend (en desarrollo):**

- [React 18](https://react.dev/) + [Vite](https://vitejs.dev/) — interfaz de usuario
- [Leaflet](https://leafletjs.com/) — visualización de rutas y árboles en mapa

**Herramientas de desarrollo:**

- [Ruff](https://github.com/astral-sh/ruff) — linting y formateo Python
- [Pyright](https://github.com/microsoft/pyright) — type checking estático
- [Pytest](https://pytest.org/) + [Coverage.py](https://coverage.readthedocs.io/) — testing
- [Commitlint](https://commitlint.js.org/) + [Husky](https://typicode.github.io/husky/) — validación de commits

---

## Problema de Investigación

En trabajos previos de censo de árboles urbanos, equipos en terreno recorrieron
sectores de la ciudad para recopilar fotografías e información técnica de los
árboles. El objetivo principal de estos censos es contribuir a la seguridad
vial mediante el monitoreo y seguimiento del estado de árboles urbanos.

Los datos recopilados conforman una base inicial de información que podrá ser
utilizada en futuras etapas para apoyar el entrenamiento de modelos de
Inteligencia Artificial orientados a la clasificación y análisis de árboles
urbanos.

Actualmente, el proyecto se encuentra en una nueva etapa: realizar un
re-censo de las zonas previamente censadas. El objetivo es actualizar la
información existente, generar nuevos registros y mantener consistencia entre
los datos históricos y los nuevos datos recopilados en terreno mediante la
planificación eficiente de rutas para equipos de censadores.

Para esto, se cuenta con bases de datos previas que contienen:

- Fotografías de árboles urbanos
- Geolocalización de cada árbol
- Información técnica recopilada en censos anteriores

Sin embargo, estas fuentes de información se encuentran distribuidas en bases
separadas y heterogéneas. El proyecto busca utilizar dichos datos como entrada
para planificar recorridos eficientes de los censadores y facilitar futuras
integraciones con nuevas bases de datos.

La tarea de re-censo presenta desafíos importantes:

- **Ineficiencia en rutas**: Los censadores deben recorrer zonas extensas,
  visitando árboles previamente registrados y nuevos puntos de interés
- **Balance de carga**: Es necesario distribuir equitativamente el trabajo
  entre equipos de terreno considerando restricciones temporales por ruta
- **Actualización de información**: Se debe garantizar consistencia entre los
  datos históricos y los nuevos registros
- **Complejidad combinatoria**: Encontrar rutas eficientes para múltiples
  censadores corresponde a un problema NP-difícil
- **Costo operacional**: Reducir tiempos y costos de desplazamiento disminuye
  costos operacionales y fatiga del personal

## Contexto

El catastro y monitoreo de árboles urbanos es una tarea relevante principalmente
para la seguridad vial y la prevención de riesgos asociados a la caída de
árboles en zonas urbanas.

En etapas anteriores del proyecto, se realizaron censos en distintas zonas
urbanas para recopilar información visual y técnica de árboles. Estos datos
constituyen una base preliminar que permitirá, en etapas futuras, desarrollar
modelos de IA orientados a la clasificación y análisis de árboles urbanos.

En esta nueva etapa, se requiere volver a recorrer las zonas ya censadas para:

- Actualizar información existente
- Verificar el estado actual de los árboles
- Obtener nuevas fotografías y registros
- Generar información más completa y consistente para futuros procesos de clasificación mediante IA

## Enfoque de Solución

El problema se modela como una variante del Multiple Traveling Salesman Problem
(mTSP) con restricciones temporales y balance de carga, resuelto mediante
programación con restricciones usando OR-Tools VRP.

El pipeline de optimización:

1. **Importación**: carga de árboles georreferenciados desde CSV o base de datos existente
2. **Matriz de costos**: consulta a OSRM para obtener tiempos de desplazamiento peatonal reales entre pares de árboles
3. **Solver VRP**: OR-Tools resuelve el ruteo multi-agente con restricciones de tiempo máximo por ruta y balance de carga
4. **Resultado**: conjunto de rutas asignadas a censadores, visualizadas en mapa con Leaflet
