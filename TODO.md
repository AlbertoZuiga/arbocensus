# TODO — Generador de Rutas Óptimas para Censo de Árboles

**Estado actual:** Pipeline P0 implementado y funcional ✅  
**Última actualización:** 2 de diciembre de 2025

---

## 📊 Estado del Proyecto

### ✅ Completado (P0 — MVP Funcional)

#### Infraestructura y Arquitectura

- [x] Estructura modular del proyecto bajo `src/arbocensus_pipeline/`
- [x] CLI completo con subcomandos por etapa
- [x] Sistema de run directories con versionado (`artifacts/runs/<id>/`)
- [x] Metadata automática en todos los outputs (timestamp, git SHA)
- [x] Symlink `latest/` apuntando a última ejecución
- [x] `.gitignore` configurado para artifacts y secrets

#### Módulos del Pipeline

- [x] **01 — Input** (`input.py`): Carga desde JSON o PostgreSQL con fallbacks
- [x] **02 — Filter** (`filter.py`): Deduplicación y validación de coordenadas
- [x] **03 — Graph** (`graph.py`): Construcción de nodos y matriz Haversine
- [x] **04 — Cluster** (`cluster.py`): Clustering recursivo por split geográfico
- [x] **05 — TSP** (`tsp.py`): Nearest Neighbor + 2-opt por cluster
- [x] **06 — Export** (`export.py`): Generación de GeoJSON para visualización

#### Utilidades

- [x] `utils.py`: Haversine, NN, 2-opt, tour_length
- [x] `io.py`: Read/write JSON con metadata, run directory management
- [x] `cli.py`: Interfaz unificada con flags `--run-id` y `--outdir`

#### Visualización

- [x] Viewer web Leaflet (`viewer/index.html`)
- [x] Carga automática desde `artifacts/runs/latest/06_output/`
- [x] Controles de capa por etapa
- [x] Popups con info de nodos y rutas
- [x] Presets de visualización (botones Stage 1-5)
- [x] Responsive y full-screen

#### Herramientas Auxiliares

- [x] `bbox_selector/`: App Flask para seleccionar áreas y exportar JSON
- [x] Soporte Docker Compose para bbox_selector
- [x] Documentación completa en README.md

#### Documentación

- [x] README.md actualizado con arquitectura completa
- [x] Explicación detallada de cada módulo
- [x] Guías de instalación y uso
- [x] Ejemplos de comandos

---

## 🚧 En Progreso

### Optimización y Calidad

- [ ] Implementar min-max global optimizer (LNS)
- [ ] Rebalanceo inter-cluster (relocate, swap, 2-opt\*)
- [ ] Evaluación comparativa de estrategias de clustering

### Testing

- [ ] Tests unitarios para cada módulo (pytest)
- [ ] Tests de integración end-to-end
- [ ] Validación automática de GeoJSON
- [ ] CI/CD con GitHub Actions

---

## 📋 Backlog (Priorizadas)

### P1 — Rutas Caminables Reales

**Objetivo:** Reemplazar Haversine con distancias reales de calles.

**Tareas:**

- [ ] Integrar OSRM local o servicio externo
- [ ] Implementar cache persistente de distancias
  - [ ] Esquema de DB (Postgres/SQLite)
  - [ ] Función de hash para pares de coordenadas
  - [ ] Mecanismo de invalidación de cache
- [ ] Agregar multiplicador configurable Haversine → Real
- [ ] Comparación empírica: Haversine vs. OSRM
  - [ ] Dataset de prueba con rutas conocidas
  - [ ] Métricas: error promedio, max error, tiempo de cómputo

**Archivos afectados:**

- `src/arbocensus_pipeline/graph.py` (compute_matrix)
- Nuevo: `src/arbocensus_pipeline/routing.py` (OSRM client)
- Nuevo: `src/arbocensus_pipeline/cache.py` (distance cache)

---

### P1 — Optimización Min-Max

**Objetivo:** Minimizar el tiempo del censante más lento.

**Tareas:**

- [ ] Implementar Large Neighborhood Search (LNS)
  - [ ] Destructor: seleccionar nodos de cluster más largo
  - [ ] Repair: insertar nodos minimizando max(T_total)
  - [ ] Criterio de aceptación: Simulated Annealing
- [ ] Operadores inter-cluster:
  - [ ] Relocate (mover 1 nodo)
  - [ ] Swap (intercambiar 2 nodos)
  - [ ] 2-opt\* (intercambiar segmentos)
- [ ] Métricas de evaluación:
  - [ ] Tiempo max antes/después
  - [ ] Desviación estándar entre censantes
  - [ ] Tiempo total del sistema

**Archivos afectados:**

- Nuevo: `src/arbocensus_pipeline/optimize.py`
- `cli.py` (nuevo subcomando `optimize`)

---

### P1 — Mejoras en Clustering

**Objetivo:** Clusters más balanceados y compactos.

**Opciones a evaluar:**

- [ ] KMeans con distancias Haversine
- [ ] KMedoids (más robusto a outliers)
- [ ] Balanced KMeans (capacitated clustering)
- [ ] Clustering jerárquico con corte adaptativo

**Evaluación:**

- [ ] Comparar compacidad (diámetro promedio)
- [ ] Comparar balance (varianza de tamaños)
- [ ] Comparar tiempo de ejecución

**Archivos afectados:**

- `src/arbocensus_pipeline/cluster.py`
- Nuevas implementaciones en submódulo `cluster/strategies/`

---

### P1 — Visualización Avanzada

**Objetivo:** Mejorar viewer y agregar análisis visual.

**Tareas:**

- [ ] Selector de run por query param (`?run=demo`)
- [ ] Comparador side-by-side de múltiples runs
- [ ] Gráficos de métricas:
  - [ ] Histograma de tiempos por censante
  - [ ] Evolución de optimización (si se implementa LNS)
  - [ ] Mapa de calor de densidad de árboles
- [ ] Exportar rutas a formatos móviles:
  - [ ] GPX para GPS
  - [ ] KML para Google Earth

**Archivos afectados:**

- `viewer/index.html`
- Nuevos: `viewer/compare.html`, `viewer/charts.js`

---

### P2 — Interfaz Web Completa

**Objetivo:** App web full-stack para configurar y ejecutar pipeline.

**Stack sugerido:**

- Frontend: React + Leaflet
- Backend: FastAPI (Python) o Flask
- DB: PostgreSQL para persistir runs

**Funcionalidades:**

- [ ] Formulario para parámetros de pipeline
- [ ] Ejecución async con progress bar
- [ ] Histórico de runs con filtros
- [ ] Descarga de outputs (JSON/GeoJSON/GPX)
- [ ] Autenticación básica (usuarios/roles)

**Estructura:**

```
web/
├── frontend/          # React app
├── backend/           # FastAPI
├── docker-compose.yml
└── README.md
```

---

### P2 — API REST

**Objetivo:** Permitir integración con sistemas externos.

**Endpoints:**

```
POST   /api/v1/pipeline/run        # Ejecutar pipeline
GET    /api/v1/pipeline/runs       # Listar runs
GET    /api/v1/pipeline/runs/:id   # Detalle de run
GET    /api/v1/pipeline/runs/:id/download/:file  # Descargar output
DELETE /api/v1/pipeline/runs/:id   # Eliminar run
```

**Documentación:**

- [ ] OpenAPI / Swagger
- [ ] Ejemplos de uso (curl, Python requests)

---

## 🔬 Investigación y Experimentos

### Benchmark de Algoritmos TSP

**Objetivo:** Evaluar trade-off calidad/tiempo de diferentes heurísticas.

**Algoritmos a comparar:**

- [x] Nearest Neighbor (baseline)
- [x] NN + 2-opt (actual)
- [ ] NN + 3-opt
- [ ] Lin-Kernighan
- [ ] Christofides
- [ ] OR-Tools CP-SAT

**Métricas:**

- Tour length (metros)
- Tiempo de ejecución (ms)
- Gap vs. óptimo (si se conoce)

**Dataset:**

- TSPLIB instances adaptadas
- Clusters reales del censo (50-200 nodos)

---

### Análisis de Sensibilidad

**Variables a analizar:**

- Número de censantes (4, 8, 12, 16)
- Tiempo por árbol (3, 5, 10 min)
- Velocidad de caminata (3, 4, 5 km/h)
- Método de clustering (recursive vs. kmeans)
- Haversine multiplier (1.0, 1.2, 1.5)

**Output:**

- Gráficos de impacto en tiempo máximo
- Recomendaciones de parámetros por escenario

---

## 🐛 Bugs Conocidos y Mejoras Menores

### Bugs

- [ ] Viewer no carga si falta algún GeoJSON (necesita graceful fallback)
- [ ] Metadata no persiste correctamente en algunos casos de error
- [ ] Dotenv warning se muestra incluso cuando .env existe

### Mejoras UX

- [ ] Progress indicator en CLI para etapas largas
- [ ] Colores consistentes entre viewer y CLI output
- [ ] Logs más detallados en modo verbose (`--verbose`)
- [ ] Validación de inputs con mensajes de error claros

### Refactoring

- [ ] Extraer constantes a archivo de config (config.py)
- [ ] Type hints completos en todos los módulos
- [ ] Docstrings en formato Google/NumPy
- [ ] Pre-commit hooks (black, flake8, mypy)

---

## 📚 Documentación Pendiente

### Tutoriales

- [ ] Quickstart video (5 min)
- [ ] Tutorial paso a paso con screenshots
- [ ] Guía de troubleshooting común

### Documentación Técnica

- [ ] Diagrama de flujo del pipeline (Mermaid/draw.io)
- [ ] Diagramas de secuencia para cada etapa
- [ ] Decisiones arquitectónicas (ADRs)

### Ejemplos

- [ ] Caso real: Censo de Providencia (Santiago)
- [ ] Caso sintético: Grid 10x10
- [ ] Comparación con método manual

---

## 🎯 Hitos del Proyecto

### Hito 1: MVP Funcional (P0) ✅ — Completado

- Pipeline completo de 6 etapas
- Viewer básico
- Documentación inicial

### Hito 2: Producción-Ready (P1) 🔜 — En progreso

- **Target:** Febrero 2026
- Distancias reales (OSRM)
- Optimización min-max
- Tests completos
- CI/CD

### Hito 3: Plataforma Web (P2) 💡 — Planeado

- **Target:** Junio 2026
- Interfaz web full-stack
- API REST
- Multi-usuario
- Deploy en cloud

---

## 🔄 Workflow de Desarrollo

### Para agregar una nueva feature:

1. **Crear issue** en GitHub con label correspondiente
2. **Crear branch**: `git checkout -b feat/nombre-feature`
3. **Desarrollar** con commits atómicos
4. **Tests**: Asegurar cobertura >80%
5. **Documentación**: Actualizar README si es necesario
6. **PR**: Crear Pull Request con descripción detallada
7. **Review**: Esperar aprobación
8. **Merge**: Squash and merge a main

### Para reportar un bug:

1. **Verificar** que no esté duplicado en Issues
2. **Crear issue** con template de bug report
3. **Incluir**:
   - Versión del código (git SHA)
   - Comando ejecutado
   - Output completo
   - Archivos de input (si es posible)

---

## 📞 Siguiente Acción Inmediata

**Prioridad 1:**

- [ ] Implementar tests básicos (input, filter, graph)
- [ ] Setup GitHub Actions para CI

**Prioridad 2:**

- [ ] Prototipo de OSRM integration
- [ ] Benchmark NN vs. NN+2opt vs. LK

**Prioridad 3:**

- [ ] Viewer con selector de runs
- [ ] Exportar a GPX

---

**Mantenedores:** [Nombre del equipo]  
**Última revisión:** 2 de diciembre de 2025
