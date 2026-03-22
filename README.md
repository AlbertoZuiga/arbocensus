# 🌳 Generador de Rutas Óptimas para Censo de Árboles

_Pipeline modular_ — _Balanceo de carga_ — _Clustering geográfico_ — _Optimización TSP_

Este proyecto implementa un sistema completo para generar rutas óptimas de censo de árboles dentro de un área urbana. El objetivo principal es distribuir equitativamente el trabajo entre múltiples censantes mediante clustering geográfico y algoritmos de optimización de rutas (TSP).

---

## 📋 Tabla de Contenidos

- [🌳 Generador de Rutas Óptimas para Censo de Árboles](#-generador-de-rutas-óptimas-para-censo-de-árboles)
  - [📋 Tabla de Contenidos](#-tabla-de-contenidos)
  - [🎯 1. Resumen del Proyecto](#-1-resumen-del-proyecto)
    - [Objetivo Principal](#objetivo-principal)
    - [Características Principales](#características-principales)
    - [Flujo de Datos](#flujo-de-datos)
  - [🏗 2. Arquitectura y Estructura](#-2-arquitectura-y-estructura)
    - [Estructura de Directorios](#estructura-de-directorios)
    - [Componentes Principales](#componentes-principales)
      - [1. **Pipeline Core** (`src/arbocensus_pipeline/`)](#1-pipeline-core-srcarbocensus_pipeline)
      - [2. **Runner Principal** (`run.py`)](#2-runner-principal-runpy)
      - [3. **Visualizador Web** (`viewer/index.html`)](#3-visualizador-web-viewerindexhtml)
  - [⚙️ 3. Instalación y Configuración](#️-3-instalación-y-configuración)
    - [Requisitos](#requisitos)
    - [Instalación](#instalación)
    - [Formateo y Hooks Locales](#formateo-y-hooks-locales)
    - [Configuración de Base de Datos (Opcional)](#configuración-de-base-de-datos-opcional)
  - [🚀 4. Uso del Sistema](#-4-uso-del-sistema)
    - [Ejecución Rápida (Pipeline Completo)](#ejecución-rápida-pipeline-completo)
    - [Parámetros del CLI](#parámetros-del-cli)
      - [`input`](#input)
      - [`filter`](#filter)
      - [`graph`](#graph)
      - [`cluster`](#cluster)
      - [`tsp`](#tsp)
      - [`export`](#export)
  - [📦 5. Módulos del Pipeline](#-5-módulos-del-pipeline)
    - [5.1 `input.py` — Carga de Datos](#51-inputpy--carga-de-datos)
    - [5.2 `filter.py` — Filtrado de Árboles](#52-filterpy--filtrado-de-árboles)
    - [5.3 `graph.py` — Construcción del Grafo](#53-graphpy--construcción-del-grafo)
    - [5.4 `cluster.py` — Clustering Geográfico](#54-clusterpy--clustering-geográfico)
    - [5.5 `tsp.py` — Optimización de Rutas](#55-tsppy--optimización-de-rutas)
    - [5.6 `export.py` — Exportación GeoJSON](#56-exportpy--exportación-geojson)
    - [5.7 `utils.py` — Utilidades Matemáticas](#57-utilspy--utilidades-matemáticas)
    - [5.8 `io.py` — Gestión de I/O y Metadata](#58-iopy--gestión-de-io-y-metadata)
    - [5.9 `cli.py` — Interfaz de Línea de Comandos](#59-clipy--interfaz-de-línea-de-comandos)
  - [🗺 6. Visualización de Resultados](#-6-visualización-de-resultados)
    - [Viewer Web (`viewer/index.html`)](#viewer-web-viewerindexhtml)
  - [🔬 7. Documentación Técnica](#-7-documentación-técnica)
    - [8.1 Algoritmos Implementados](#81-algoritmos-implementados)
      - [Clustering: Recursive Split](#clustering-recursive-split)
      - [TSP: Nearest Neighbor + 2-opt](#tsp-nearest-neighbor--2-opt)
    - [8.2 Métricas de Distancia](#82-métricas-de-distancia)
      - [Haversine (Implementación Actual - P0)](#haversine-implementación-actual---p0)
      - [Rutas Caminables Reales (Roadmap P1)](#rutas-caminables-reales-roadmap-p1)
    - [8.3 Cálculo de Tiempos](#83-cálculo-de-tiempos)
    - [8.4 Formato de Datos](#84-formato-de-datos)
      - [Input JSON (`01_input.json`)](#input-json-01_inputjson)
      - [Graph JSON (`03_graph.json`)](#graph-json-03_graphjson)
      - [Routes JSON (`routes_by_cluster.json`)](#routes-json-routes_by_clusterjson)
    - [8.5 Optimizaciones Futuras](#85-optimizaciones-futuras)
      - [Min-Max Global](#min-max-global)
      - [Cache de Distancias](#cache-de-distancias)
      - [Paralelización](#paralelización)
    - [8.6 Testing y Validación](#86-testing-y-validación)
  - [📚 8. Referencias y Recursos](#-8-referencias-y-recursos)
    - [Algoritmos](#algoritmos)
    - [Herramientas](#herramientas)
    - [Librerías Python](#librerías-python)
  - [🤝 9. Contribución](#-9-contribución)
    - [🌐 Convenciones de Idioma](#-convenciones-de-idioma)
    - [Estructura de Commits](#estructura-de-commits)
    - [Workflow](#workflow)
  - [📞 10. Contacto y Soporte](#-10-contacto-y-soporte)

---

## 🎯 1. Resumen del Proyecto

### Objetivo Principal

Generar rutas óptimas para el censo de árboles urbanos, distribuyendo equitativamente el trabajo entre N censantes mediante:

- **Clustering geográfico** basado en capacidad y proximidad
- **Optimización de rutas** usando heurísticas TSP (Nearest Neighbor + 2-opt)
- **Cálculo de tiempos** considerando distancias caminables y tiempo de censo por árbol

### Características Principales

- ✅ **Pipeline modular** con 6 etapas independientes
- ✅ **Entrada flexible**: archivo JSON o base de datos PostgreSQL
- ✅ **Clustering recursivo** por división espacial con balanceo de capacidad
- ✅ **Optimización TSP** usando NN + 2-opt para cada cluster
- ✅ **Exportación GeoJSON** para visualización en mapas interactivos
- ✅ **Viewer web** (Leaflet) para inspeccionar resultados por etapa
- ✅ **Metadata tracking** con versionado git y timestamps automáticos

### Flujo de Datos

```bash
Input (JSON/DB) → Filtrado → Grafo → Clustering → TSP → Export (GeoJSON)
     ↓               ↓          ↓         ↓         ↓          ↓
01_input.json → 02_filtered → 03_graph → 04_clusters → 05_routes → 06_output/
```

---

## 🏗 2. Arquitectura y Estructura

### Estructura de Directorios

```bash
mi_proyecto/
├── src/
│   └── arbocensus_pipeline/          # Package principal del pipeline
│       ├── __init__.py
│       ├── cli.py                     # CLI para ejecutar etapas
│       ├── input.py                   # Carga de datos (DB/file)
│       ├── filter.py                  # Filtrado de árboles
│       ├── graph.py                   # Construcción de grafo y matriz
│       ├── cluster.py                 # Clustering geográfico
│       ├── tsp.py                     # Algoritmos TSP (NN + 2-opt)
│       ├── export.py                  # Exportación a GeoJSON
│       ├── io.py                      # Utilidades I/O + metadata
│       └── utils.py                   # Funciones auxiliares (haversine, 2-opt)
├── viewer/
│   └── index.html                     # Visualizador web Leaflet
├── bbox_selector/                     # App Flask para selección de áreas
│   ├── app.py
│   ├── templates/
│   ├── Dockerfile
│   └── docker-compose.yml
├── artifacts/
│   └── runs/
│       ├── <run-id>/                  # Outputs por ejecución
│       │   ├── 01_bbox_input/
│       │   ├── 02_filtered.json
│       │   ├── 03_graph.json
│       │   ├── clusters_by_censantes.json
│       │   ├── routes_by_cluster.json
│       │   └── 06_output/             # GeoJSON para viewer
│       └── latest/                    # Symlink a última ejecución
├── secrets/                           # Credenciales (no en git)
│   ├── arbocensus.env
│   └── heatmap_database_url.txt
├── run.py                             # Runner principal (delega a CLI)
├── saved_bbox.json                    # Bbox de ejemplo (fallback)
├── README.md
└── TODO.md
```

### Componentes Principales

#### 1. **Pipeline Core** (`src/arbocensus_pipeline/`)

Módulos Python que implementan cada etapa del procesamiento:

| Módulo       | Responsabilidad                                                            |
| ------------ | -------------------------------------------------------------------------- |
| `input.py`   | Carga bbox y árboles desde archivo JSON o base de datos PostgreSQL         |
| `filter.py`  | Elimina duplicados y valida coordenadas; filtra puntos dentro del polígono |
| `graph.py`   | Construye lista de nodos y matriz de distancias (Haversine)                |
| `cluster.py` | Divide nodos en clusters balanceados usando split recursivo                |
| `tsp.py`     | Resuelve TSP por cluster con Nearest Neighbor + 2-opt                      |
| `export.py`  | Genera GeoJSON de puntos, rutas, bbox y polígonos de clusters              |
| `io.py`      | Helpers para lectura/escritura con metadata automática                     |
| `utils.py`   | Funciones matemáticas (haversine, NN, 2-opt, route_length)                 |
| `cli.py`     | Interfaz de línea de comandos para ejecutar cada etapa                     |

#### 2. **Runner Principal** (`run.py`)

Script top-level que:

- Inserta `src/` en `sys.path` automáticamente
- Delega toda la ejecución al módulo `arbocensus_pipeline.cli`
- Permite ejecutar el pipeline sin configurar `PYTHONPATH`

```bash
./run.py input --bbox saved_bbox.json --out artifacts/01_input.json
```

#### 3. **Visualizador Web** (`viewer/index.html`)

Aplicación Leaflet standalone que:

- Carga GeoJSON desde `artifacts/runs/latest/06_output/`
- Muestra capas: bbox, input, filtered, clusters, routes
- Permite alternar entre etapas del pipeline
- Soporta hover, popups y controles de capa

---

## ⚙️ 3. Instalación y Configuración

### Requisitos

- Python 3.12.11
- `venv` con nombre `venv/` en la raíz del proyecto
- Node.js + npm (para Husky y Commitlint)
- PostgreSQL (opcional, para lectura directa de DB)
- Navegador moderno (para el viewer)

### Instalación

```bash
# Clonar repositorio
git clone https://github.com/AlbertoZuiga/arbocensus
cd arbocensus

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias del pipeline
pip install -r requirements.txt

# Instalar herramientas de formato/lint
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

Comandos útiles:

```bash
# Formatear archivos Python
black .
isort .

# Verificar sin modificar archivos
black --check .
isort --check-only .

# Ejecutar los hooks manualmente sobre todo el repo
./venv/bin/python -m pre_commit run --all-files
```

### Configuración de Base de Datos (Opcional)

Si quieres cargar árboles directamente desde PostgreSQL:

Crea archivo `.env` en la raíz:

```bash
ARBOCENSUS_DB_URL=postgres://user:pass@host:5432/db_name
ARBOCENSUS_API_DB_URL=postgres://user:pass@host:5432/api_db
```

El pipeline intentará conectarse usando estas credenciales. Si fallan, usará el archivo `saved_bbox.json` como fallback.

---

## 🚀 4. Uso del Sistema

### Ejecución Rápida (Pipeline Completo)

```bash
# En caso de no pasar parametros a los comando se usaran los parametros por default

# 1. Cargar datos de entrada
./run.py input --bbox saved_bbox.json --out artifacts/01_input.json --run-id demo

# 2. Filtrar árboles
./run.py filter --inp artifacts/runs/demo/01_bbox_input/01_input.json \
  --out 02_filtered.json --run-id demo

# 3. Construir grafo
./run.py graph --inp artifacts/runs/demo/02_filtered.json \
  --out 03_graph.json --run-id demo

# 4. Clustering (8 censantes)
./run.py cluster --inp artifacts/runs/demo/03_graph.json \
  --out clusters_by_censantes.json --num 8 --run-id demo

# 5. Resolver TSP
./run.py tsp --inp artifacts/runs/demo/03_graph.json \
  --clusters artifacts/runs/demo/clusters_by_censantes.json \
  --out routes_by_cluster.json --run-id demo

# 6. Exportar GeoJSON
./run.py export --graph artifacts/runs/demo/03_graph.json \
  --routes artifacts/runs/demo/routes_by_cluster.json \
  --outdir artifacts/runs/demo/06_output --run-id demo

# 7. Abrir viewer
python -m http.server 5500
# open viewer/index.html # O abrir directamente (si el navegador lo permite)
```

### Parámetros del CLI

#### `input`

- `--bbox PATH`: Ruta al JSON con bbox y árboles (default: `saved_bbox.json`)
- `--out PATH`: Archivo de salida (default: `input.json`)
- `--run-id ID`: Identificador de ejecución (crea `artifacts/runs/<ID>/`)
- `--max N`: Máximo de árboles a cargar desde DB (default: 500)

#### `filter`

- `--inp PATH`: Archivo de entrada (default: `input.json`)
- `--out PATH`: Archivo de salida (default: `filtered.json`)

#### `graph`

- `--inp PATH`: Archivo filtrado (default: `filtered.json`)
- `--out PATH`: Archivo de salida (default: `graph.json`)

#### `cluster`

- `--inp PATH`: Grafo de entrada (default: `graph.json`)
- `--out PATH`: Archivo de salida (default: `clusters_by_censantes.json`)
- `--num N`: Número de censantes (default: 8)

#### `tsp`

- `--inp PATH`: Grafo (default: `graph.json`)
- `--clusters PATH`: Archivo de clusters (default: `clusters_by_censantes.json`)
- `--out PATH`: Archivo de salida (default: `tsp.json`)
- `--time-per-tree MINS`: Tiempo de censo por árbol (default: 5 min)
- `--walking-speed KMH`: Velocidad caminata (default: 4 km/h)

#### `export`

- `--graph PATH`: Grafo con nodos (default: `graph.json`)
- `--routes PATH`: Rutas TSP (default: `cluster_by_censantes.json`)
- `--outdir DIR`: Directorio de salida para GeoJSON

---

## 📦 5. Módulos del Pipeline

### 5.1 `input.py` — Carga de Datos

**Funciones principales:**

- `load_input(bbox_path, max_results=500, use_secrets=False)`: Carga bbox y árboles desde archivo JSON o base de datos
- `load_env()`: Carga variables de entorno desde `.env` (requiere python-dotenv)
- `_get_conn_from_env()`: Obtiene conexión PostgreSQL desde variables de entorno
- `_query_dbs()`: Consulta tablas de árboles y combina resultados

**Flujo:**

1. Intenta cargar desde archivo `bbox_path` (ej: `saved_bbox.json`)
2. Si falla o está vacío, intenta conectar a base de datos:
   - Lee `ARBOCENSUS_DB_URL` y `ARBOCENSUS_API_DB_URL`
   - Como fallback, lee `secrets/heatmap_database_url.txt`
   - Consulta tablas de árboles y deduplica por ID
3. Retorna dict con: `{"north", "south", "east", "west", "trees": [...]}`

**Output:** `input.json`

---

### 5.2 `filter.py` — Filtrado de Árboles

**Funciones principales:**

- `filter_trees(obj)`: Filtra árboles duplicados y valida coordenadas
- `point_in_poly(x, y, poly)`: Verifica si un punto está dentro de un polígono (ray casting)

**Filtros aplicados:**

- Elimina duplicados por ID
- Descarta árboles sin coordenadas válidas
- (Opcional) Verifica que el punto esté dentro del polígono geográfico

**Output:** `filtered.json`

---

### 5.3 `graph.py` — Construcción del Grafo

**Funciones principales:**

- `build_nodes(trees)`: Convierte lista de árboles en nodos numerados
- `compute_matrix(nodes)`: Calcula matriz simétrica NxN de distancias Haversine

**Detalles:**

- Usa distancia Haversine (en metros) como métrica baseline (P0)
- Matriz simétrica: `M[i][j] = M[j][i]`
- Complejidad: O(n²) para n árboles

**Output:** `graph.json`

```json
{
  "nodes": [{"id": 0, "lat": -33.45, "lng": -70.66, "meta": {...}}],
  "distances": [[0, 150.2, ...], [150.2, 0, ...]]
}
```

---

### 5.4 `cluster.py` — Clustering Geográfico

**Funciones principales:**

- `make_clusters_recursive(nodes, max_size)`: Divide nodos en clusters balanceados
- `recursive_split(node_list, nodes, max_size, out_clusters)`: Split recursivo por eje más largo
- `reorder_by_nn(cluster_members, distances)`: Reordena miembros del cluster con NN
- `bounding_box(nodes)`: Calcula bbox de un conjunto de nodos
- `longest_axis(nodes)`: Determina si dividir por latitud o longitud

**Algoritmo:**

1. Calcula bounding box del conjunto de nodos
2. Identifica el eje más largo (lat o lng)
3. Ordena nodos por ese eje y divide por la mediana
4. Repite recursivamente hasta que cada cluster tenga ≤ `max_size` nodos

**Output:** `clusters_by_censantes.json`

```json
{
  "clusters": [
    {"cluster_id": 0, "members": [0, 5, 12, ...], "size": 62},
    {"cluster_id": 1, "members": [1, 3, 8, ...], "size": 63}
  ]
}
```

---

### 5.5 `tsp.py` — Optimización de Rutas

**Funciones principales:**

- `compute_route_for_cluster(members, distances, time_per_tree, walking_speed_kmh, haversine_multiplier)`: Resuelve TSP para un cluster

**Algoritmo:**

1. **Nearest Neighbor (NN)**: Genera route inicial greedy
2. **2-opt**: Mejora el route eliminando cruces
3. Calcula métricas:
   - `route_meters`: Distancia total en metros
   - `route_minutes`: Tiempo caminando
   - `service_minutes`: Tiempo censando árboles
   - `total_minutes`: Suma de ambos

**Parámetros:**

- `time_per_tree`: Minutos por árbol (default: 5)
- `walking_speed_kmh`: Velocidad de caminata (default: 4 km/h)
- `haversine_multiplier`: Factor de ajuste para distancia real vs. Haversine (default: 1.0)

**Output:** `routes_by_cluster.json`

```json
{
  "routes": [
    {
      "cluster_id": 0,
      "route": [0, 12, 5, 18, ...],
      "size": 62,
      "route_meters": 4823.5,
      "route_minutes": 72.3,
      "service_minutes": 310.0,
      "total_minutes": 382.3
    }
  ]
}
```

---

### 5.6 `export.py` — Exportación GeoJSON

**Funciones principales:**

- `build_points_geojson_from_nodes(nodes, clusters_map)`: Crea GeoJSON de puntos con cluster_id
- `build_routes_geojson(nodes, routes)`: Crea GeoJSON de LineStrings para rutas
- `write_geojson(obj, path)`: Escribe GeoJSON a archivo

**Outputs generados:**

- `bbox.geojson`: Polígono del área de trabajo
- `input_points.geojson`: Todos los puntos originales
- `filtered_points.geojson`: Puntos después del filtrado
- `clusters.geojson`: Puntos coloreados por cluster
- `routes.geojson`: LineStrings de cada ruta TSP
- `cluster_polygons.geojson`: (Opcional) Polígonos convexos de clusters

---

### 5.7 `utils.py` — Utilidades Matemáticas

**Funciones principales:**

- `haversine_m(lat1, lon1, lat2, lon2)`: Distancia entre dos puntos en metros
- `nn_route(start, nodes, distances)`: Genera route con algoritmo Nearest Neighbor
- `two_opt(route, distances, max_iter=100)`: Mejora route eliminando cruces
- `route_length(route, distances)`: Calcula longitud total de un route (incluyendo retorno)

**Detalles técnicos:**

- **Haversine**: Usa radio terrestre de 6371 km
- **NN**: Greedy O(n²), siempre visita el nodo más cercano no visitado
- **2-opt**: Intercambia pares de aristas, itera hasta no encontrar mejoras

---

### 5.8 `io.py` — Gestión de I/O y Metadata

**Funciones principales:**

- `write_json(obj, path, params=None)`: Escribe JSON con metadata automática
- `read_json(path)`: Lee JSON desde archivo
- `make_run_dir(base='artifacts/runs', run_id=None)`: Crea directorio para ejecución
- `sha256_of_file(path)`: Calcula hash de archivo (para cache)

**Metadata automática (`__meta__`):**

```json
{
  "__meta__": {
    "created_at": "2025-12-02T10:30:45Z",
    "pipeline_version": "a3f2b1c...",
    "params": { "bbox": "saved_bbox.json", "num_censantes": 8 }
  }
}
```

**Run directories:**

- Crea `artifacts/runs/<run-id>/` con timestamp único
- Actualiza symlink `artifacts/runs/latest/` apuntando a la última ejecución
- Permite reproducibilidad y comparación entre ejecuciones

---

### 5.9 `cli.py` — Interfaz de Línea de Comandos

**Subcomandos disponibles:**

| Comando   | Descripción               | Inputs                | Output                       |
| --------- | ------------------------- | --------------------- | ---------------------------- |
| `input`   | Carga datos desde file/DB | `--bbox`, `--max`     | `input.json`                 |
| `filter`  | Filtra y deduplica        | `--inp`               | `filtered.json`              |
| `graph`   | Construye grafo           | `--inp`               | `graph.json`                 |
| `cluster` | Crea clusters             | `--inp`, `--num`      | `clusters_by_censantes.json` |
| `tsp`     | Resuelve rutas            | `--inp`, `--clusters` | `routes_by_cluster.json`     |
| `export`  | Genera GeoJSON            | `--graph`, `--routes` | `output/*.geojson`           |

**Flags globales:**

- `--run-id ID`: Identificador de ejecución (crea subdir en artifacts)
- `--outdir DIR`: Directorio base para outputs (default: `artifacts/runs`)

---

## 🗺 6. Visualización de Resultados

### Viewer Web (`viewer/index.html`)

**Características:**

- ✅ Mapa Leaflet con tiles CartoDB Voyager
- ✅ Carga automática desde `artifacts/runs/latest/output/`
- ✅ Controles de capa para cada etapa
- ✅ Popups con información de nodos y rutas
- ✅ Presets por etapa (botones 1-5)
- ✅ Hover effects en rutas
- ✅ Responsive y full-screen

**Capas disponibles:**

- **BBox**: Límites del área de trabajo (línea punteada)
- **Input**: Puntos originales (gris)
- **Filtered**: Puntos filtrados (verde)
- **Nodos**: Puntos coloreados por cluster
- **Clusters**: Polígonos de clusters (semi-transparentes)
- **Rutas**: LineStrings coloreados por cluster

**Uso:**

```bash
# Opción 2: Servir con HTTP server
python -m http.server 5500

# Opción 1: Abrir directamente (si el navegador permite file://)
open viewer/index.html

# Luego abrir: http://localhost:5500/viewer/index.html
```

**Presets de etapas:**

- **Stage 1**: Muestra Input + BBox
- **Stage 2**: Muestra Filtered + BBox
- **Stage 3**: Muestra Nodos del grafo
- **Stage 4**: Muestra Clusters + Nodos
- **Stage 5**: Muestra Rutas + Clusters + Nodos

---

## 🔬 7. Documentación Técnica

### 8.1 Algoritmos Implementados

#### Clustering: Recursive Split

**Estrategia:** Divide espacialmente los nodos hasta alcanzar capacidad máxima por cluster.

**Pasos:**

1. Calcular bounding box de todos los nodos
2. Identificar eje más largo (latitud o longitud)
3. Ordenar nodos por ese eje
4. Dividir en la mediana
5. Repetir recursivamente en cada mitad

**Ventajas:**

- Simple y rápido O(n log n)
- Produce clusters geográficamente compactos
- Balanceo automático de tamaños

**Desventajas:**

- No considera distancias reales (solo coordenadas)
- Puede crear clusters subóptimos en zonas irregulares

---

#### TSP: Nearest Neighbor + 2-opt

**Nearest Neighbor:**

1. Comenzar en nodo arbitrario
2. Visitar siempre el nodo no visitado más cercano
3. Retornar al inicio

**Complejidad:** O(n²)
**Calidad:** Aproximación 1.5-2x del óptimo

**2-opt (Mejora local):**

1. Tomar dos aristas del route
2. Eliminarlas y reconectar de forma cruzada
3. Si mejora el route, aceptar cambio
4. Repetir hasta convergencia

**Complejidad:** O(n² × iteraciones)
**Calidad:** Elimina cruces evidentes, mejora 20-40% sobre NN

**Resultado combinado:**

- NN da route inicial rápido
- 2-opt refina eliminando ineficiencias
- Calidad razonable para clusters de <200 nodos

---

### 8.2 Métricas de Distancia

#### Haversine (Implementación Actual - P0)

**Fórmula:**

```bash
a = sin²(Δφ/2) + cos φ₁ × cos φ₂ × sin²(Δλ/2)
c = 2 × atan2(√a, √(1−a))
d = R × c
```

Donde:

- φ = latitud en radianes
- λ = longitud en radianes
- R = 6371 km (radio terrestre)

**Características:**

- Distancia "en línea recta" sobre la esfera terrestre
- No considera calles, edificios, ni topografía
- Error típico: +20-40% vs. distancia caminable real

**Uso recomendado:**

- Prototipado rápido
- Áreas pequeñas (<5 km²)
- Cuando no se requiere precisión absoluta

---

#### Rutas Caminables Reales (Roadmap P1)

**Opciones:**

1. **Google Distance Matrix API**
   - Ventaja: Rutas reales, considerando calles
   - Desventaja: Costoso (0.01 USD/request), límites estrictos

2. **OSRM (Open Source Routing Machine)**
   - Ventaja: Gratis, instalable localmente
   - Desventaja: Requiere servidor, datos OSM actualizados

3. **Valhalla / GraphHopper**
   - Similar a OSRM, diferentes trade-offs

**Estrategia recomendada para P1:**

- Usar Haversine para clustering inicial
- Calcular matriz de distancias reales solo para nodos en mismo cluster
- Cachear resultados para evitar requests repetidos

---

### 8.3 Cálculo de Tiempos

**Fórmula del tiempo total por censante:**

```bash
T_total = T_servicio + T_ruta

Donde:
T_servicio = n_arboles × tiempo_por_arbol
T_ruta = distancia_metros × (60 min/h) / (1000 m/km) / velocidad_kmh
```

**Parámetros configurables:**

- `tiempo_por_arbol`: 3-10 minutos (default: 5)
- `velocidad_kmh`: 3-5 km/h (default: 4)
- `haversine_multiplier`: 1.0-1.5 (ajuste empírico para distancia real)

**Ejemplo:**

- 50 árboles × 5 min = 250 min servicio
- 3000 m × 60 / 1000 / 4 = 45 min ruta
- **Total: 295 min (~5 horas)**

---

### 8.4 Formato de Datos

#### Input JSON (`01_input.json`)

```json
{
  "north": -33.40,
  "south": -33.50,
  "east": -70.60,
  "west": -70.70,
  "polygon": {
    "type": "Polygon",
    "coordinates": [[[lng, lat], ...]]
  },
  "trees": [
    {
      "id": 123,
      "lat": -33.4567,
      "lng": -70.6543,
      "species": "Platanus orientalis",
      "...": "otros campos opcionales"
    }
  ],
  "__meta__": {
    "created_at": "2025-12-02T10:30:00Z",
    "pipeline_version": "abc123"
  }
}
```

#### Graph JSON (`03_graph.json`)

```json
{
  "nodes": [
    {"id": 0, "lat": -33.45, "lng": -70.66, "meta": {...}},
    {"id": 1, "lat": -33.46, "lng": -70.67, "meta": {...}}
  ],
  "distances": [
    [0, 150.2, 280.5],
    [150.2, 0, 190.3],
    [280.5, 190.3, 0]
  ]
}
```

#### Routes JSON (`routes_by_cluster.json`)

```json
{
  "routes": [
    {
      "cluster_id": 0,
      "route": [0, 5, 12, 8, 3],
      "size": 5,
      "route_meters": 823.4,
      "route_minutes": 12.3,
      "service_minutes": 25.0,
      "total_minutes": 37.3
    }
  ]
}
```

---

### 8.5 Optimizaciones Futuras

#### Min-Max Global

**Objetivo:** Minimizar el tiempo del censante más lento.

**Estrategia:**

1. Después de TSP inicial, identificar cluster más largo
2. Aplicar operadores de rebalanceo:
   - **Relocate**: mover 1 nodo a otro cluster
   - **Swap**: intercambiar nodos entre clusters
   - **2-opt\***: intercambiar segmentos entre rutas
3. Aceptar cambio si reduce max(T_total)

**Implementación:** LNS (Large Neighborhood Search)

---

#### Cache de Distancias

Para evitar recalcular distancias:

```python
# Usar hash de coordenadas como key
def cache_key(lat1, lon1, lat2, lon2):
    return f"{lat1:.6f},{lon1:.6f}-{lat2:.6f},{lon2:.6f}"

# Guardar en archivo o DB
cache = {}
if key in cache:
    return cache[key]
else:
    dist = compute_real_distance(lat1, lon1, lat2, lon2)
    cache[key] = dist
    return dist
```

---

#### Paralelización

**Oportunidades:**

- TSP por cluster (cada uno independiente)
- Cálculo de distancias (por pares)
- Evaluación de operadores de búsqueda local

**Implementación Python:**

```python
from multiprocessing import Pool

def solve_cluster_tsp(cluster):
    return compute_route_for_cluster(...)

with Pool(8) as p:
    routes = p.map(solve_cluster_tsp, clusters)
```

---

### 8.6 Testing y Validación

**Checklist de validación:**

- [ ] Todo árbol aparece exactamente una vez en los clusters
- [ ] routes no tienen duplicados (excepto inicio/fin)
- [ ] Distancias son simétricas: `M[i][j] == M[j][i]`
- [ ] Coordenadas están en rango válido (lat: -90 a 90, lng: -180 a 180)
- [ ] GeoJSON es válido (validar con geojsonlint.com)
- [ ] Metadata contiene timestamp y versión
- [ ] `black --check .` no reporta cambios pendientes
- [ ] `isort --check-only .` no reporta imports desordenados

**Validación automática disponible en el repositorio:**

```bash
# Ejecutar chequeos de formato localmente antes de abrir un PR
black --check .
isort --check-only .

# Ejecutar los hooks de pre-commit sobre todo el proyecto
./venv/bin/python -m pre_commit run --all-files
```

En Pull Requests hacia `main`, GitHub Actions replica estos chequeos usando la versión de Python definida en `.python-version`.

**Tests unitarios sugeridos:**

```python
# test_clustering.py
def test_all_nodes_assigned():
    clusters = make_clusters_recursive(nodes, max_size=50)
    all_members = [m for c in clusters for m in c]
    assert len(all_members) == len(nodes)
    assert len(set(all_members)) == len(nodes)

# test_tsp.py
def test_route_is_valid():
    route = nn_route(0, [0,1,2,3], distances)
    assert len(route) == 4
    assert len(set(route)) == 4
```

---

## 📚 8. Referencias y Recursos

### Algoritmos

- **TSP**: Applegate et al., "The Traveling Salesman Problem: A Computational Study" (2006)
- **2-opt**: Croes, "A Method for Solving Traveling-Salesman Problems" (1958)
- **Lin-Kernighan**: Lin & Kernighan, "An Effective Heuristic Algorithm for TSP" (1973)

### Herramientas

- [OSRM](http://project-osrm.org/) - Routing engine
- [Leaflet](https://leafletjs.com/) - JavaScript mapping library
- [GeoJSON.io](http://geojson.io/) - GeoJSON validator/editor
- [OR-Tools](https://developers.google.com/optimization) - Google optimization library

### Librerías Python

- `psycopg2` - PostgreSQL adapter
- `python-dotenv` - Environment variables
- `geojson` - GeoJSON utilities (opcional)

---

## 🤝 9. Contribución

### 🌐 Convenciones de Idioma

Para mantener consistencia en el proyecto:

- **Código (Python, JS, etc.)**: todo en inglés (nombres de variables, funciones, clases, comentarios técnicos breves).
- **Commits**: en inglés, siguiendo Conventional Commits.
- **Branches**: en inglés (ej: `feat/add-clustering-heuristic`, `fix/tsp-bug`).
- **Pull Requests (título y descripción)**: en inglés.
- **Documentación (README, docs/, explicaciones extensas)**: en español.

**Resumen:**

- Inglés → ejecución (código + workflow técnico)
- Español → comunicación y documentación

Esto permite:

- Mejor compatibilidad con tooling y comunidad global
- Mayor claridad para el equipo local en documentación

### Estructura de Commits

```bash
tipo(scope): descripción breve

Descripción detallada (opcional)
```

**Tipos:**

- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `refactor`: Refactorización sin cambio funcional
- `docs`: Cambios en documentación
- `perf`: Mejora de performance

Los hooks del repositorio validan estos mensajes con `commitlint`. Un ejemplo válido:

```bash
git commit -m "docs(readme): documenta formateo y hooks locales"
```

> ⚠️ Todos los commits deben estar en inglés.

### Workflow

1. Fork del repositorio
2. Crear branch (en inglés): `git checkout -b feat/my-feature`
3. Crear y activar `venv`, luego instalar dependencias Python y `npm install`
4. Trabajar normalmente; el hook `pre-commit` formatea/valida Python antes de cada commit
5. Hacer commits en inglés usando tipos permitidos por `commitlint`
6. Verificar localmente con `black --check .` e `isort --check-only .`
7. Push: `git push origin feat/my-feature`
8. Crear Pull Request (en inglés) hacia `main`

---

## 📞 10. Contacto y Soporte

- **Issues:** [GitHub Issues](https://github.com/AlbertoZuiga/arbocensus/issues)
- **Documentación:** Este README y archivos en `docs/`
- **Email:** [azuiga@miuandes.cl](azuiga@miuandes.cl)

---

**Última actualización:** 22 de marzo de 2026
