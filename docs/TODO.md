# TODO — Routing Algorithm Migration

**Objetivo:** Migrar el pipeline de generación de rutas P0 hacia la arquitectura V3 descrita en `pseudo-codigo.md`.  
**Estado:** Implementación en progreso. Phase 1 completada.  
**Última actualización:** 21 de marzo de 2026

---

## Contexto

El pipeline actual (P0) implementa una versión simplificada e incorrecta del VRP:

| Componente              | P0 (actual)                                          | V3 (objetivo)                                                      |
| ----------------------- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| Clustering              | Recursive bounding-box split (sin balanceo temporal) | K-Means Constrained (balanceo espacial, `n_clusters` dinámico)     |
| TSP                     | NN + 2-opt en route **cerrado**                      | NN + 2-opt en path **abierto**                                     |
| Distancias              | Matriz densa Haversine O(n²)                         | Grafo sparse KD-tree O(n·k)                                        |
| Evaluación              | Una sola pasada Haversine                            | Multi-fidelidad: Euclidiana → OSM → Google                         |
| Routing API             | Ninguna                                              | OSRM (loop de optimización) + Google Directions (validación final) |
| Control loop            | Inexistente (`--num` fijo)                           | Ajuste dinámico de `n_routes` con banda objetivo + histéresis      |
| Optimización inter-ruta | Ninguna                                              | Operadores relocate + swap entre rutas                             |
| Tiempo de servicio      | Calculado pero no influye en balanceo                | Incluido en duración total; impacta el ajuste de `n_routes`        |
| Restricciones de tiempo | Ninguno                                              | Banda `lower/upper` + `hard_max_duration` opcional                 |

### Módulos que se mantienen sin cambios

- `input.py` — Carga de árboles desde JSON/PostgreSQL
- `filter.py` — Deduplicación y filtro por polígono
- `io.py` — Lectura/escritura JSON con metadata, run directories
- `export.py` — Generación de GeoJSON (posible update menor para rutas abiertas)

### Referencia de pseudocódigo

El archivo `pseudo-codigo.md` contiene cuatro versiones del algoritmo (V0–V3). La implementación debe seguir **V3** fielmente. Las funciones clave descritas en V3 son:

- `find_routes` — Orquestador principal
- `compute_route_time_with_cache` — Evaluación de tiempo con cache
- `nearest_neighbor_path` — TSP heurístico abierto
- `two_opt_path` — Mejora local en path abierto
- `k_means_constrained` — Clustering balanceado
- `build_kd_tree` / `build_sparse_graph_from_kdtree` — Grafo sparse
- `relocate_nodes_between_routes` / `swap_nodes_between_routes` — Búsqueda local inter-ruta
- `estimate_euclidean_tsp` — Estimación rápida de carga de trabajo

---

## Estructura de archivos después de la migración

```bash
src/arbocensus_pipeline/
├── __init__.py      # sin cambios
├── cli.py           # modificado: nuevo subcomando `route` (Phase 6)
├── cluster.py       # modificado: agregar k_means_constrained (Phase 3)
├── export.py        # sin cambios (o ajuste menor para rutas abiertas)
├── filter.py        # sin cambios
├── graph.py         # modificado: agregar build_kd_tree, build_sparse_graph (Phase 2)
├── input.py         # sin cambios
├── io.py            # sin cambios
├── optimize.py      # NUEVO: relocate, swap, find_routes (V3) (Phases 5 + 6)
├── routing.py       # NUEVO: clientes OSM/Google, RoutingCache (Phase 4)
├── tsp.py           # modificado: usar open-path variants (Phase 1)
└── utils.py         # modificado: agregar funciones open-path y estimate (Phase 1)
```

---

## Phase 1 — Open-Path TSP

**Estado:** Completada (21 de marzo de 2026)

### Objetivo

Corregir el error algorítmico más crítico: el TSP actual genera routes cerrados (el último nodo se conecta con el primero). Las rutas de censo son caminos abiertos: el censante empieza en un extremo y termina en otro.

### Complejidad: Baja

### Dependencias: Ninguna (es la base de todo)

### Archivos a modificar

- `src/arbocensus_pipeline/utils.py`
- `src/arbocensus_pipeline/tsp.py`

### Archivos a crear

Ninguno.

### Tareas

- [x] **1.1** Actualizar la función `route_length(route, distances)` en `utils.py`
  - **Sin** sumar `distances[route[-1]][route[0]]`
  - Solo suma las aristas `route[i] → route[i+1]` para `i` de `0` a `len(route)-2`
  - Retorna `float` con la distancia total del camino abierto en metros
  - Si `route` está vacío o tiene un solo nodo, retorna `0.0`

- [x] **1.2** Reemplazar la función `nn_route(...)` por `nn_path(start, nodes, distances)` en `utils.py`
  - Algoritmo idéntico al `nn_route` existente (greedy nearest neighbor)
  - La diferencia conceptual es que se documenta como camino abierto (sin intención de cerrar)
  - Parámetros: `start: int` (nodo inicial), `nodes: List[int]` (nodos a visitar), `distances: List[List[float]]` (matriz)
  - Retorna `List[int]` con el orden de visita
  - El nodo `start` debe ser el primer elemento de la lista retornada
  - Nota: la selección del mejor nodo de inicio puede hacerse externamente probando todos los nodos como `start` y quedándose con el `route_length` más corto

- [x] **1.3** Actualizar la función `two_opt(route, distances, max_iter=100)` en `utils.py`
  - Implementar 2-opt local search para **path abierto**
  - El movimiento 2-opt revierte un segmento `route[i:j+1]` y compara longitudes
  - No se considera la arista de cierre `route[-1] → route[0]` en ningún cálculo de costo
  - Parámetros: `route: List[int]`, `distances: List[List[float]]`, `max_iter: int`
  - Retorna `List[int]` con la ruta mejorada

- [x] **1.4** Agregar la función `estimate_euclidean_tsp(nodes)` en `utils.py`
  - Recibe `nodes: List[Dict]` donde cada dict tiene `lat` y `lng`
  - Calcula un route greedy NN sobre distancias Haversine entre todos los nodos
  - Retorna `float` con la distancia total estimada en **kilómetros** (no metros)
  - Usar `haversine_m` existente, dividir resultado por 1000
  - Aplicar factor de tortuosidad urbana `1.3` (calles no son línea recta)
  - Este valor se usa en V3 para estimar `n_routes` inicial

- [x] **1.5** Actualizar `compute_route_for_cluster` en `tsp.py`
  - Reemplazar `nn_route` por `nn_path`
  - Reemplazar `route_length` por `route_length`
  - Reemplazar `two_opt` por `two_opt`
  - La firma y estructura del dict retornado se mantienen idénticas
  - Los campos `route_meters` y `route_minutes` ahora reflejan camino abierto

- [x] **1.6** Verificar que `export.py` → `build_routes_geojson` funciona correctamente con rutas abiertas
  - Las rutas abiertas siguen siendo listas de índices de nodo, por lo que `LineString` GeoJSON se genera igual
  - Confirmar visualmente en el viewer que las rutas no dibujan un segmento de cierre fantasma

### Notas de implementación

- Las funciones legacy (`route_length`, `nn_route`, `two_opt`) **no se eliminan**. Se mantienen para backward compatibility con el subcomando `tsp` existente.
- Los tests de Phase 7 deben verificar que para un path lineal de 3 nodos `[A, B, C]`, `route_length` retorna `d(A,B) + d(B,C)` y **no** `d(A,B) + d(B,C) + d(C,A)`.

### Criterios de aceptación

1. `route_length([0, 1, 2], mat)` retorna la suma de solo 2 aristas (no 3)
2. `nn_path` produce una ruta válida que visita todos los nodos exactamente una vez
3. `two_opt` produce rutas de longitud abierta ≤ la del input
4. `estimate_euclidean_tsp` retorna un valor en km mayor que 0 para un conjunto de nodos no trivial
5. `compute_route_for_cluster` genera rutas abiertas (campo `route_meters` < valor anterior cerrado para mismos datos)
6. El viewer muestra rutas sin segmento de cierre

### Riesgos

- **Bajo**: Cambio puramente algorítmico sin dependencias externas. El mayor riesgo es un off-by-one en los rangos de iteración de `two_opt`.

---

## Phase 2 — Sparse Graph (KD-Tree)

### Objetivo

Reemplazar la matriz de distancias densa O(n²) con un grafo sparse basado en KD-tree. Para 1000 nodos, la matriz densa tiene 1.000.000 entradas; el grafo sparse con k=12 vecinos tiene solo 12.000. Esto reduce memoria y permite escalar a decenas de miles de árboles.

### Complejidad: Media

### Dependencias: Phase 1 (las funciones TSP deben poder operar sobre el grafo sparse)

### Archivos a modificar

- `src/arbocensus_pipeline/graph.py`
- `src/arbocensus_pipeline/utils.py`

### Archivos a crear

Ninguno.

### Tareas

- [x] **2.1** Agregar la función `build_kd_tree(nodes)` en `graph.py`
  - Recibe `nodes: List[Dict]` con campos `lat`, `lng`
  - Crea un array numpy con las coordenadas `[[lat, lng], ...]`
  - Retorna un objeto `scipy.spatial.KDTree` construido sobre ese array
  - Importar `scipy.spatial.KDTree`; agregar `scipy` a `requirements.txt` si no existe

- [x] **2.2** Agregar la función `build_sparse_graph_from_kdtree(nodes, kd_tree, k_neighbors=12)` en `graph.py`
  - Para cada nodo `i`, consultar los `k_neighbors` vecinos más cercanos en el KD-tree
  - Calcular la distancia real Haversine para cada par (no la distancia euclidiana del KD-tree, que opera en grados)
  - Retornar un `dict[int, list[tuple[int, float]]]`: adjacency list donde la clave es el node_id y el valor es lista de `(neighbor_id, distance_meters)`
  - Asegurar simetría: si `i` es vecino de `j`, entonces `j` debe ser vecino de `i`
  - Nota: `KDTree.query(k=k_neighbors+1)` retorna el nodo mismo como primer vecino; descartarlo

- [x] **2.3** Agregar función `sparse_distance(graph, i, j)` en `utils.py`
  - Busca la distancia entre nodos `i` y `j` en el grafo sparse
  - Si la arista `(i, j)` existe, retorna su peso
  - Si no existe (nodos no son vecinos en el grafo), calcula Haversine on-the-fly como fallback
  - Esto permite que NN y 2-opt funcionen con el grafo sparse sin requerir la matriz completa

- [x] **2.4** Agregar variantes de las funciones TSP que operen sobre el grafo sparse
  - `nn_path_sparse(start, nodes, sparse_graph, all_nodes)` — usa `sparse_distance` como lookup de costo
  - `two_opt_sparse(route, sparse_graph, all_nodes, max_iter=100)` — evalúa movimientos usando `sparse_distance`
  - `route_length_sparse(route, sparse_graph, all_nodes)` — suma costos usando `sparse_distance`
  - El parámetro `all_nodes` es la lista completa de nodos (para poder calcular Haversine como fallback)

- [x] **2.5** Marcar `compute_matrix` como deprecated
  - Agregar un docstring que indique: `"Deprecated: use build_kd_tree + build_sparse_graph for O(n·k) performance"`
  - No eliminar la función (el subcomando `graph` del CLI la usa)

- [x] **2.6** Introducir flag global `--v3` en el CLI
  - Controla el uso de la nueva implementación de grafo (`run_stage_graph_v3`)
  - Default: desactivado (usa matriz densa legacy)
  - Objetivo: permitir migración incremental sin romper pipelines existentes. Este flag debe propagarse hasta el orquestador V3 (Phase 6) para activar todo el pipeline nuevo (clustering, grafo sparse, routing y optimización inter-ruta).

- [x] **2.7** Agregar `scipy` a `requirements.txt` (si no está ya)

### Notas de implementación

- El KD-tree opera en coordenadas (lat, lng) que son grados, no metros. Los vecinos más cercanos en grados son una buena aproximación de los vecinos más cercanos en metros para zonas geográficas pequeñas (una ciudad). Para mayor precisión, se podrían proyectar a UTM, pero no es necesario para este proyecto.
- El parámetro `k_neighbors=12` es el default de V3. Debe ser configurable desde el CLI.
- El grafo sparse se construye **una sola vez** al inicio de `find_routes` y se reutiliza en todas las iteraciones.

### Criterios de aceptación

1. `build_kd_tree` retorna un objeto `KDTree` válido
2. `build_sparse_graph` retorna un dict con exactamente `len(nodes)` claves
3. Cada nodo tiene entre `k_neighbors` y `2 * k_neighbors` vecinos (por simetría, puede tener más que k)
4. `sparse_distance(graph, i, j)` retorna el mismo valor que `haversine_m(nodes[i], nodes[j])` para pares que existen en el grafo
5. `nn_path_sparse` produce la misma ruta que `nn_path` con la matriz densa para k suficientemente grande (k ≥ n-1)
6. El uso de memoria del grafo sparse es < 5% del uso de la matriz densa para n=1000

### Riesgos

- **Medio**: La representación interna cambia de matriz a adjacency list. Las funciones de Phase 1 que usan `distances[i][j]` no funcionan directamente con el grafo sparse; por eso se crean variantes `_sparse`.
- **Medio**: Si `k_neighbors` es demasiado bajo, el grafo puede ser desconectado, causando que NN se atasque. Mitigación: validar conectividad; si hay nodos aislados, incrementar k localmente.

---

## Phase 3 — Balanced Clustering (K-Means Constrained)

### Objetivo

Reemplazar el clustering recursivo por bounding-box split con K-Means Constrained, que produce clusters espacialmente compactos y de tamaño balanceado. El número de clusters `n_clusters` es determinado dinámicamente por el orquestador V3 (no por el usuario).

### Complejidad: Media

### Dependencias: Ninguna directa (puede ejecutarse en paralelo con Phases 2 y 4)

### Archivos a modificar

- `src/arbocensus_pipeline/cluster.py`

### Archivos a crear

Ninguno.

### Tareas

- [x] **3.0** Agregar dependencias a `requirements.txt`
  - `k-means-constrained>=0.7.0`
  - `scikit-learn>=1.0` (dependencia de k-means-constrained, pero listarla explícitamente)
  - `numpy>=1.21`

- [x] **3.1** Agregar la función `k_means_constrained(nodes, n_clusters)` en `cluster.py`
  - Recibe `nodes: List[Dict]` con campos `lat`, `lng` y `n_clusters: int`
  - Extraer coordenadas en un array numpy `[[lat, lng], ...]`
  - Usar la librería `k-means-constrained` (PyPI: `k_means_constrained`): `KMeansConstrained(n_clusters=n_clusters, size_min=min_size, size_max=max_size)`
  - Calcular `min_size = floor(len(nodes) / n_clusters)` y `max_size = ceil(len(nodes) / n_clusters) + 1`
  - Fit sobre las coordenadas, obtener labels
  - Retornar `List[List[int]]` donde cada sub-lista contiene los índices de nodos del cluster
  - **Mismo formato de salida** que `make_clusters_recursive` para compatibilidad

- [x] **3.2** Implementar fallback para edge cases
  - Si `n_clusters >= len(nodes)`: retornar un cluster por nodo (cada cluster es `[[i]]`)
  - Si `n_clusters <= 0`: levantar `ValueError`
  - Si `n_clusters == 1`: retornar `[list(range(len(nodes)))]`
  - ~~Si `k-means-constrained` no converge (excepciones): hacer fallback a `sklearn.cluster.KMeans` estándar sin constraints~~

- [x] **3.3** Agregar funciones de métricas de calidad de clustering
  - `cluster_diameter(cluster_indices, nodes)` → `float`: distancia máxima (Haversine) entre cualquier par de nodos del cluster
  - `cluster_balance_score(clusters)` → `float`: `max(sizes) - min(sizes)` donde `sizes = [len(c) for c in clusters]`; un score de 0 es perfectamente balanceado

- [x] **3.4** Marcar `make_clusters_recursive` y `recursive_split` como deprecated
  - Agregar docstring: `"Deprecated: use k_means_constrained for balanced spatial clustering"`
  - No eliminar (el subcomando `cluster` del CLI las usa)

- [x] **3.5** Integrar la ejecución de `k_means_constrained` bajo el flag `--v3`
  - Asegurar que, cuando el flag `--v3` esté activado, el pipeline utilice `k_means_constrained` en lugar de `make_clusters_recursive`
  - Mantener el comportamiento actual (legacy) como default cuando `--v3` esté desactivado
  - Preparar la integración para que el orquestador **V3** (Phase 6) controle dinámicamente `n_clusters`

### Notas de implementación

- K-Means Constrained minimiza la varianza intra-cluster con restricciones de tamaño min/max por cluster. Esto es superior al split recursivo que solo considera la extensión geográfica del bounding box.
- Las coordenadas se pasan directamente en (lat, lng). K-Means usa distancia euclidiana sobre grados, lo cual es una aproximación aceptable para áreas dentro de una misma ciudad (error < 1% para Santiago de Chile).
- El `n_clusters` no es fijo: será determinado y ajustado por el orquestador V3 en cada iteración del loop principal.

### Criterios de aceptación

1. `k_means_constrained(nodes, 4)` retorna exactamente 4 clusters
2. La unión de todos los clusters contiene todos los índices `0..len(nodes)-1` sin repetir
3. El tamaño de cada cluster está entre `floor(n/k)` y `ceil(n/k)+1`
4. `cluster_balance_score` es 0 o 1 para datasets uniformes
5. `cluster_diameter` retorna un valor > 0 para clusters con más de 1 nodo
6. El fallback funciona si la librería k-means-constrained falla

### Riesgos

- **Medio**: La librería `k-means-constrained` puede no estar instalada en todos los entornos. Mitigación: el fallback a `sklearn.cluster.KMeans` asegura que el pipeline no se rompe.
- **Bajo**: Para datasets muy pequeños (n < 10, k = 3), K-Means puede no converger de forma estable. Mitigación: el fallback por edge cases (task 3.2).

---

## Phase 4 — Routing Clients (OSRM + Google + Cache)

### Objetivo

Implementar los dos backends de routing externos que V3 requiere: un cliente OSRM para evaluación dentro del loop de optimización (costo bajo, precisión media) y un cliente Google Directions para validación final (costo alto, precisión alta). Ambos con cache persistente.

### Complejidad: Alta

### Dependencias: Ninguna directa (puede ejecutarse en paralelo con Phases 2 y 3)

### Archivos a crear

- `src/arbocensus_pipeline/routing.py`

### Archivos a modificar

- `.env.example` (documentar variables de entorno requeridas)

### Tareas

- [x] **4.0** Agregar `Requests==2.32.5` a `requirements.txt`

- [x] **4.1** Crear la clase `RoutingCache` en `routing.py`
  - Almacena resultados de queries de routing para evitar llamadas repetidas a APIs
  - Estructura interna: `dict` con clave `(origin_lat_round7, origin_lng_round7, dest_lat_round7, dest_lng_round7, mode)` y valor `{"distance_m": float, "duration_s": float, "source": str}`
  - `mode` es string: `"walking"`, `"driving"`, etc.
  - Método `get(origin, dest, mode) → Optional[dict]`: busca en cache
  - Método `put(origin, dest, mode, result)`: guarda en cache
  - Método `save_to_disk(path)`: serializa todo el cache a JSON en `path`
  - Método `load_from_disk(path)`: carga cache desde JSON; si el archivo no existe, inicializa vacío
  - Las coordenadas se redondean a 7 decimales para el key (precisión ~1cm)
  - El cache debe ser thread-safe: usar `threading.Lock` en `get` y `put`

- [x] **4.2** Implementar la función `haversine_fallback_route_time(origin, dest, cache, walking_speed_kmh=4.5, multiplier=1.3)` en `routing.py`
  - Calcula duración usando `haversine_m(origin, dest) * multiplier / (walking_speed_kmh * 1000 / 3600)`
  - No hace ninguna llamada de red
  - Se usa como fallback cuando OSM y Google no están disponibles
  - Guarda en cache con `source="haversine_fallback"`

- [x] **4.3** Agregar variables a `.env.example`

  ```bash
  OSRM_BASE_URL=http://router.project-osrm.org
  GOOGLE_MAPS_API_KEY=your-api-key-here
  OSRM_RATE_LIMIT_MS=100
  ```

- [x] **4.4** Implementar la función `osm_route_time(origin, dest, cache, base_url=None)` en `routing.py`
  - `origin` y `dest` son dicts con `lat` y `lng`
  - Primero busca en `cache`; si existe, retorna `duration_s` directamente
  - Si no está en cache, hace request HTTP GET a OSRM:
    - URL default: `http://router.project-osrm.org/route/v1/foot/{lng1},{lat1};{lng2},{lat2}?overview=false`
    - Nota: OSRM usa `foot` profile para caminata
    - Si `base_url` es proporcionado, usar ese en vez del público
  - Parsear la respuesta JSON: `response["routes"][0]["duration"]` (en segundos)
  - Guardar en cache con `source="osrm"`
  - Retornar duración en **segundos** (float)
  - Si la request falla (timeout, error HTTP, OSRM no disponible), retornar fallback: Haversine × 1.3 / walking_speed. Log warning.
  - Timeout de request: 5 segundos
  - Rate limiting: implementar un `time.sleep(0.1)` entre requests consecutivos (para el API público; desactivable para instancias locales)

- [x] **4.5** Implementar la función `google_route_time(origin, dest, cache, api_key=None)` en `routing.py`
  - Primero busca en `cache`; si existe, retorna `duration_s`
  - Si no está en cache, hace request a Google Directions API:
    - Endpoint: `https://maps.googleapis.com/maps/api/directions/json`
    - Params: `origin={lat},{lng}`, `destination={lat},{lng}`, `mode=walking`, `key={api_key}`
  - Parsear: `response["routes"][0]["legs"][0]["duration"]["value"]` (en segundos)
  - Guardar en cache con `source="google"`
  - Retornar duración en **segundos** (float)
  - Si `api_key` es `None`, leer de `os.getenv("GOOGLE_MAPS_API_KEY")`
  - Si la key no existe o la request falla, retornar fallback Haversine × 1.3 / walking_speed. Log warning.
  - **Nunca llamar a Google dentro del loop de optimización** — solo en validación final (Phase 6 controla esto)

- [x] **4.6** Implementar la función `compute_route_time(route, f_route_time, cache, t_per_tree)` en `routing.py`
  - Implementación directa de `compute_route_time_with_cache` del pseudocódigo V3
  - `route: List[Dict]` — lista ordenada de nodos (cada uno con `lat`, `lng`)
  - `f_route_time` — función callable que toma `(origin_dict, dest_dict, cache)` y retorna duración en segundos
  - Itera sobre pares consecutivos `route[i] → route[i+1]` (path abierto: no cierra)
  - Suma `total_travel_time` (en segundos) de todos los pares
  - Suma `total_service_time = len(route) * t_per_tree` (en segundos)
  - Retorna `total_travel_time + total_service_time` en **segundos**

### Notas de implementación

- El cache es la pieza más importante de este módulo. Sin cache, el loop de optimización (10+ iteraciones × cientos de pares por iteración) haría miles de requests a OSRM. Con cache, la mayoría de pares se evalúan solo una vez.
- El `RoutingCache` debe persistir a disco entre ejecuciones del pipeline. Se sugiere guardarlo en `artifacts/runs/<run_id>/routing_cache.json`.
- Google Directions API cobra por request. El diseño de V3 garantiza que solo se llame en la validación final (una vez por arista de las rutas finales). Para 8 rutas de 50 nodos cada una, son ~400 requests, costando aprox. $2 USD.
- OSRM público tiene rate limits no documentados. Para uso intensivo, se recomienda levantar una instancia local con Docker: `docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/chile-latest.osrm`.

### Criterios de aceptación

1. `RoutingCache` persiste y carga desde JSON correctamente
2. `osm_route_time` retorna un valor > 0 para dos puntos dentro de Santiago
3. `osm_route_time` retorna fallback Haversine cuando OSRM no responde
4. `google_route_time` retorna un valor > 0 con una API key válida
5. `compute_route_time` retorna la suma correcta de travel time + service time
6. La segunda llamada a `osm_route_time` con los mismos puntos no genera una HTTP request (cache hit)
7. El cache es thread-safe (no falla con acceso concurrente)

### Riesgos

- **Alto**: Dependencia de APIs externas. OSRM público puede estar caído o rate-limitear. Mitigación: fallback a Haversine y opción de instancia local.
- **Medio**: Google API key es un secreto que no debe committearse. Mitigación: leer de `.env`; el pipeline funciona sin ella (skip validación final).
- **Bajo**: El cache puede crecer mucho para datasets grandes. Mitigación: es solo un dict de floats; 100K entries ≈ 10MB en JSON.

---

## Phase 5 — Inter-Route Optimization

### Objetivo

Implementar operadores de búsqueda local que mueven o intercambian nodos entre rutas para mejorar el balance de duraciones. Estos operadores se aplican después del clustering y TSP intra-cluster, pero antes de evaluar el criterio de convergencia.

### Complejidad: Media-Alta

### Dependencias: Phase 1 (open-path TSP), Phase 2 (sparse graph)

### Archivos a crear

- `src/arbocensus_pipeline/optimize.py`

### Tareas

- [x] **5.1** Implementar la función auxiliar `insertion_cost(node, route, position, sparse_graph, all_nodes)` en `optimize.py`
  - Calcula el costo delta de insertar `node` en `route` en la posición `position`
  - Si `position == 0`: costo = `sparse_distance(graph, node, route[0])`
  - Si `position == len(route)`: costo = `sparse_distance(graph, route[-1], node)`
  - Si `0 < position < len(route)`: costo = `sparse_distance(graph, route[position-1], node) + sparse_distance(graph, node, route[position]) - sparse_distance(graph, route[position-1], route[position])`
  - Retorna `float` con el delta de distancia

- [x] **5.2** Implementar la función auxiliar `removal_cost(node_index_in_route, route, sparse_graph, all_nodes)` en `optimize.py`
  - Calcula el costo delta de remover el nodo en posición `node_index_in_route` de `route`
  - Si es el primer nodo: savings = `sparse_distance(graph, route[0], route[1])`
  - Si es el último nodo: savings = `sparse_distance(graph, route[-2], route[-1])`
  - Si es un nodo intermedio: savings = `sparse_distance(graph, route[idx-1], route[idx]) + sparse_distance(graph, route[idx], route[idx+1]) - sparse_distance(graph, route[idx-1], route[idx+1])`
  - Retorna `float` negativo (ahorro) o positivo (la ruta se acorta)

- [x] **5.3** Implementar `relocate_nodes_between_routes(routes, durations, sparse_graph, all_nodes, upper_bound)` en `optimize.py`
  - Identifica la ruta con mayor duración (ruta fuente)
  - Para cada nodo en la ruta fuente:
    - Calcula el ahorro de removerlo
    - Para cada otra ruta (ruta destino):
      - Si `durations[destino] + insertion_cost < upper_bound`:
        - Encuentra la mejor posición de inserción (menor `insertion_cost`)
        - Si el movimiento reduce `max(durations)`, ejecutarlo
  - Aplica movimientos greedily (uno por iteración)
  - Repetir hasta que no se encuentre mejora o se alcancen 50 iteraciones
  - Retorna `(routes_modified, durations_modified)` — las listas actualizadas
  - **No recalcular duración completa con OSM en cada movimiento**: usar los deltas de costo en sparse_graph como aproximación

- [x] **5.4** Implementar `swap_nodes_between_routes(routes, durations, sparse_graph, all_nodes, upper_bound)` en `optimize.py`
  - Para cada par de rutas `(r1, r2)`:
    - Para cada nodo `a` en `r1` y cada nodo `b` en `r2`:
      - Calcular delta de remover `a` de `r1` e insertar `b` en su lugar
      - Calcular delta de remover `b` de `r2` e insertar `a` en su lugar
      - Si ambas rutas resultantes están bajo `upper_bound` y `max(duration_r1_new, duration_r2_new) < max(duration_r1, duration_r2)`:
        - Ejecutar el swap
  - Aplica swaps greedily
  - Repetir hasta que no se encuentre mejora o se alcancen 50 iteraciones
  - Retorna `(routes_modified, durations_modified)`
  - Optimización: solo evaluar swaps entre la ruta más larga y las demás (reduce de O(n²·m²) a O(n·m²))

- [x] **5.5** Implementar función wrapper `local_search_inter_route(routes, durations, sparse_graph, all_nodes, upper_bound)` en `optimize.py`
  - Ejecuta `relocate_nodes_between_routes` seguido de `swap_nodes_between_routes`
  - Este es el punto de entrada que usará el orquestador V3
  - Retorna `(routes, durations)` mejorados

### Notas de implementación

- Los operadores usan `sparse_distance` (Phase 2) para evaluar deltas, no OSM. Esto es correcto porque dentro del loop de optimización, la re-evaluación fina con OSM se hace **después** de los operadores (step 3.4 del pseudocódigo V3).
- Los deltas de costo son aproximados (distancia Haversine del sparse graph, no tiempo real de calles). Esto es intencional: la evaluación precisa con OSM se hace una sola vez por iteración completa.
- Un swap es más costoso computacionalmente que un relocate, pero puede encontrar mejoras que relocate no puede. Ejecutar relocate primero reduce el espacio de búsqueda para swap.

### Criterios de aceptación

1. `relocate_nodes_between_routes` reduce (o no cambia) la duración máxima entre todas las rutas
2. `swap_nodes_between_routes` reduce (o no cambia) la duración máxima
3. Después de ambos operadores, todas las rutas siguen conteniendo los mismos nodos que antes (conservación)
4. Ningún nodo aparece en más de una ruta después de la optimización
5. Si todas las rutas están bajo `upper_bound`, los operadores retornan sin cambios
6. Para un caso de 2 rutas donde una tiene 80% de carga y otra 120%, el relocate mueve nodos hasta equilibrar

### Riesgos

- **Medio-Alto**: Los deltas de costo pueden no reflejar fielmente el cambio real en duración OSM. Mitigación: el loop del orquestador recalcula con OSM después de los operadores, verificando que la mejora es real.
- **Medio**: En edge cases (rutas de 1-2 nodos), los operadores pueden intentar mover el único nodo, dejando una ruta vacía. Mitigación: no ejecutar relocate si la ruta fuente tiene ≤ 2 nodos.

---

## Phase 6 — Routing Orchestrator

### Objetivo

Implementar la función principal `find_routes` que orquesta todo el pipeline: estimación inicial → loop de optimización (clustering + open-path TSP + evaluación OSM + ajustes inter-ruta + ajuste dinámico de `n_routes` con histéresis) → validación final con Google. También agregar el subcomando `route` al CLI.

### Complejidad: Media

### Dependencias: Phases 1, 2, 3, 4, 5 (todas)

### Archivos a modificar

- `src/arbocensus_pipeline/optimize.py` (agregar `find_routes`)
- `src/arbocensus_pipeline/cli.py` (agregar subcomando `route` y soportar flag global `--v3`)

### Tareas

- [x] **6.1** Implementar `find_routes` en `optimize.py`
  - Firma exacta:

    ```python
    def find_routes(
        locations,
        expected_duration_per_route,
        t_per_tree,
        f_google_route_time,
        f_osm_route_time,
        lower_factor=0.90,
        upper_factor=1.10,
        k_neighbors: int = 12,
        max_iterations: int = 14,
        hysteresis_rounds: int = 2,
        hard_max_duration: Optional[float] = None,
    ) -> List[Tuple[List[Dict], float]]:
    ```

  - [x] **Step 0 — Inicialización**
    - Crear `osm_cache = RoutingCache()` y `google_cache = RoutingCache()`
    - Calcular `lower_bound = expected_duration_per_route * lower_factor`
    - Calcular `upper_bound = expected_duration_per_route * upper_factor`
    - Calcular `hard_upper_limit = hard_max_duration or upper_bound`
    - Inicializar mejores soluciones:
      - `best_feasible_solution = None`, `best_feasible_score = inf`
      - `best_overall_solution = None`, `best_overall_gap = inf`
    - Inicializar histéresis: `over_counter`, `under_counter`, `last_direction`
  - [x] **Step 1 — Estimación inicial**
    - `total_euclidean_km = estimate_euclidean_tsp(locations)`
    - `walking_speed_kmh = 4.0`
    - `travel_time_estimate = (total_euclidean_km / walking_speed_kmh) * 3600`
    - `service_time_estimate = len(locations) * t_per_tree`
    - `total_time_estimate = travel_time_estimate + service_time_estimate`
    - `n_routes = max(1, ceil(total_time_estimate / expected_duration_per_route))`
  - [x] **Step 2 — Grafo sparse**
    - `kd_tree = build_kd_tree(locations)`
    - `sparse_graph = build_sparse_graph_from_kdtree(locations, kd_tree, k_neighbors)`
  - [x] **Step 3 — Loop principal** (`for iteration in range(max_iterations):`)
    - **3.1** `clusters = k_means_constrained(locations, n_clusters=n_routes)`
    - **3.2** Para cada cluster: `route = nearest_neighbor_path(...)` → `route = two_opt_path(...)`
    - **3.3** Evaluar duración por ruta con `compute_route_time_with_cache(..., f_osm_route_time, osm_cache, t_per_tree)`
    - **3.4** Aplicar `relocate_nodes_between_routes(..., upper_bound)` y luego `swap_nodes_between_routes(..., upper_bound)`
    - **3.5** Recalcular duraciones OSM después de ajustes
    - **3.6** Métricas:
      - `max_route = max(durations)`, `min_route = min(durations)`, `avg_route = mean(durations)`
      - `spread = max_route - min_route`
      - `over_gap = max(0, max_route - upper_bound)`
      - `under_gap = max(0, lower_bound - min_route)`
      - `band_gap = over_gap + under_gap`
      - `feasible_score = avg_route + 0.25 * spread`
    - **3.7** Guardar mejores soluciones:
      - Si `band_gap < best_overall_gap`: actualizar `best_overall_solution`
      - Si solución factible (`max_route <= upper_bound`, `min_route >= lower_bound`, `max_route <= hard_upper_limit`) y `feasible_score` mejora: actualizar `best_feasible_solution`
    - **3.8** Convergencia: si factible, `break`
    - **3.9** Ajuste de `n_routes` con histéresis:
      - Si `max_route > upper_bound`: acumular `over_counter`
      - Elif `min_route < lower_bound`: acumular `under_counter`
      - Si `over_counter >= hysteresis_rounds`: aumentar `n_routes`
        - Si `avg_route > upper_bound`: aumento proporcional `ceil(n_routes * (avg_route/expected_duration_per_route - 1))`
        - Si no, aumentar en `+1`
      - Elif `under_counter >= hysteresis_rounds`: disminuir `n_routes` en `1` (mínimo `1`)
      - Aplicar regla de amortiguación cuando cambia el sentido de ajuste (`last_direction`)
  - [x] **Step 4 — Validación final con Google**
    - Elegir `final_routes = best_feasible_solution if best_feasible_solution else best_overall_solution`
    - Para cada ruta en `final_routes`: llamar `compute_route_time_with_cache(..., f_google_route_time, google_cache, t_per_tree)`
    - Guardar caches a disco
    - Retornar `List[Tuple[route_nodes, duration_google]]`

- [x] **6.2** Implementar función de logging para el loop
  - Al inicio de cada iteración: `print(f"Iteration {iteration+1}/{max_iterations}: n_routes={n_routes}")`
  - Al final de cada iteración: `print(f"  max={max_route:.0f}s min={min_route:.0f}s avg={avg_route:.0f}s band_gap={band_gap:.0f}s")`
  - Al hacer break por convergencia: `print(f"Converged at iteration {iteration+1} (feasible solution found)")`
  - Al terminar sin converger: `print(f"Warning: did not converge after {max_iterations} iterations, returning best available solution")`

- [ ] **6.3** Agregar el subcomando `route` a `cli.py`
  - Registrar un nuevo subparser `route` en la función `main()`
  - Argumentos:
    - `--inp` (default: `FILTER_DEFAULT_PATH`) — archivo de entrada
    - `--out` (default: `artifacts/runs/latest/route/routes.json`) — archivo de salida
    - `--max-duration` (float, required) — duración máxima por ruta en **minutos**
    - `--time-per-tree` (float, default: `2.0`) — tiempo por foto en **minutos**
    - `--lower-factor` (float, default: `0.90`) — factor de banda inferior
    - `--upper-factor` (float, default: `1.10`) — factor de banda superior
    - `--k-neighbors` (int, default: `12`) — vecinos para el grafo sparse
    - `--max-iter` (int, default: `14`) — iteraciones máximas
    - `--hysteresis-rounds` (int, default: `2`) — rondas para confirmar ajuste de `n_routes`
    - `--hard-max-duration` (float, default: `None`) — límite duro absoluto en **minutos** (opcional)
    - `--osm-url` (str, default: `None`)
    - `--use-google` (flag, default: `False`)
    - `--cache-dir` (str, default: `None`)
  - Función `run_stage_route(args)`:
  - El flag global `--v3` debe activar este subcomando como implementación preferida y permitir, en el futuro, redirigir otros subcomandos (`tsp`, `cluster`) hacia las implementaciones V3 sin romper compatibilidad.
    - Cargar árboles desde `args.inp` (JSON con key `trees`)
    - Construir `nodes` con `graph.build_nodes(trees)`
    - Convertir duraciones a segundos: `expected_s = args.max_duration * 60`, `tpt_s = args.time_per_tree * 60`
    - Si viene `hard_max_duration`: `hard_max_s = args.hard_max_duration * 60`
    - Crear callables parciales para `f_osm_route_time` y `f_google_route_time` usando las funciones de `routing.py`
    - Si `--use-google` no está activado, `f_google_route_time` = `haversine_fallback_route_time`
    - Llamar `find_routes(nodes, expected_s, tpt_s, f_google, f_osm, lower_factor=..., upper_factor=..., hysteresis_rounds=..., hard_max_duration=hard_max_s, ...)`
    - Convertir resultado a formato compatible con `export.py`:

      ```python
      {"routes": [{"route": [node_indices...], "total_minutes": dur/60, "cluster_id": i, "size": len(route)} ...]}
      ```

    - Escribir con `io.write_json`

- [ ] **6.4** Asegurar compatibilidad de salida con el viewer existente
  - El output JSON del subcomando `route` debe tener la misma estructura que el output del subcomando `tsp`
  - Campos requeridos por `export.py` → `build_routes_geojson`: `route` (lista de indices), `cluster_id`, `size`, `total_minutes`
  - Agregar campos adicionales: `travel_seconds`, `service_seconds`, `total_seconds`, `validated_by` (`"osm"` o `"google"`)

### Notas de implementación

- Las duraciones internas de `find_routes` se manejan en **segundos** (consistente con las APIs de routing). La conversión a minutos solo ocurre en la capa de CLI/output.
- El parámetro `t_per_tree` en el CLI se expresa en **minutos** (más intuitivo para el usuario), pero se convierte a segundos antes de pasarlo al orquestador.
- El orquestador no conoce la fuente de datos (no hace I/O); recibe nodos y funciones callable. Esto permite testear con mocks.
- La función `find_routes` es determinista si se fija el random seed de K-Means (que por default usa `random_state=42` en k-means-constrained).

### Criterios de aceptación

1. `find_routes` retorna una lista no vacía de `(route, duration)` tuples
2. Todos los nodos de entrada aparecen exactamente una vez en las rutas de salida
3. El loop se detiene cuando encuentra una solución factible dentro de la banda (`lower_bound <= route <= upper_bound`) respetando `hard_upper_limit`
4. El loop no excede `max_iterations`
5. Si `--use-google` no está activado, no se hace ninguna request a Google
6. El output JSON del subcomando `route` es cargable por `export.py` → `build_routes_geojson`
7. El viewer muestra las rutas generadas por el nuevo subcomando correctamente
8. `n_routes` se ajusta dinámicamente con histéresis (sube con exceso sostenido y baja con defecto sostenido)

### Riesgos

- **Medio**: La integración de 5 fases puede exponer bugs en las interfaces entre módulos. Mitigación: tests unitarios por fase (Phase 7) y un integration test end-to-end.
- **Bajo**: Si OSM está caído y no hay cache, todos los tiempos serán Haversine fallback, lo cual es menos preciso pero no crashea.

---

## Phase 7 — Testing and Validation

### Objetivo

Crear un suite de tests que valide cada componente individualmente y el sistema integrado. Permitir regresiones futuras sin romper la arquitectura V3.

### Complejidad: Media

### Dependencias: Phases 1–6 (todas implementadas)

### Archivos a crear

- `tests/test_utils_path.py`
- `tests/test_sparse_graph.py`
- `tests/test_clustering.py`
- `tests/test_routing.py`
- `tests/test_optimize.py`
- `tests/test_find_routes.py`
- `tests/conftest.py` (fixtures compartidas)

### Archivos a modificar

- `requirements.txt` (agregar `pytest>=7.0`)

### Tareas

- [ ] **7.0** Configurar pytest
  - Agregar `pytest.ini` o sección en `pyproject.toml`:

    ```ini
    [pytest]
    testpaths = tests
    python_files = test_*.py
    ```

  - Verificar que `python -m pytest tests/` ejecuta todos los tests correctamente

- [ ] **7.1** Crear `tests/conftest.py` con fixtures compartidas
  - `sample_nodes_grid()` — genera una grilla de 5×5 = 25 nodos con coordenadas equiespaciadas alrededor de (-33.45, -70.65) (Santiago)
  - `sample_nodes_linear()` — genera 10 nodos en línea recta
  - `sample_distance_matrix(nodes)` — genera matriz Haversine densa para esos nodos
  - `sample_sparse_graph(nodes)` — genera grafo sparse con k=6

- [ ] **7.2** Tests para Phase 1 — `tests/test_utils_path.py`
  - `test_route_length_does_not_close` — verifica que no suma arista de cierre
  - `test_route_length_single_node` — retorna 0
  - `test_route_length_two_nodes` — retorna una sola arista
  - `test_nn_path_visits_all` — todos los nodos presentes en output
  - `test_nn_path_no_duplicates` — no repite nodos
  - `test_two_opt_improves_or_maintains` — longitud abierta resultante ≤ input
  - `test_estimate_euclidean_tsp_positive` — retorna km > 0
  - `test_estimate_euclidean_tsp_single_node` — retorna 0

- [ ] **7.3** Tests para Phase 2 — `tests/test_sparse_graph.py`
  - `test_build_kd_tree_returns_kdtree` — tipo correcto
  - `test_build_sparse_graph_has_all_nodes` — dict tiene len(nodes) keys
  - `test_sparse_graph_symmetric` — si `j` in `graph[i]`, entonces `i` in `graph[j]`
  - `test_sparse_graph_distances_match_haversine` — las distancias del grafo coinciden con haversine_m
  - `test_sparse_distance_fallback` — para nodos no vecinos, retorna haversine

- [ ] **7.4** Tests para Phase 3 — `tests/test_clustering.py`
  - `test_k_means_constrained_correct_k` — retorna exactamente n_clusters clusters
  - `test_k_means_constrained_all_nodes_assigned` — unión de clusters = todos los nodos
  - `test_k_means_constrained_no_duplicates` — ningún nodo en más de un cluster
  - `test_k_means_constrained_balanced_sizes` — max_size - min_size ≤ 2
  - `test_k_means_constrained_edge_case_single_cluster` — n_clusters=1 funciona
  - `test_cluster_balance_score` — score = 0 para clusters iguales

- [ ] **7.5** Tests para Phase 4 — `tests/test_routing.py`
  - `test_routing_cache_put_and_get` — almacena y recupera correctamente
  - `test_routing_cache_miss` — retorna None para key inexistente
  - `test_routing_cache_save_load_disk` — persiste a JSON y recarga
  - `test_compute_route_time_sum` — suma correcta de travel + service
  - `test_osm_route_time_with_mock` — usar `unittest.mock.patch` para simular respuesta OSRM
  - `test_osm_route_time_fallback_on_error` — retorna Haversine fallback si OSRM falla
  - `test_google_route_time_with_mock` — simular respuesta Google

- [ ] **7.6** Tests para Phase 5 — `tests/test_optimize.py`
  - `test_insertion_cost_at_start` — verifica costo de inserción al inicio
  - `test_insertion_cost_at_end` — verifica costo de inserción al final
  - `test_insertion_cost_in_middle` — verifica delta correcto
  - `test_relocate_conserves_nodes` — mismos nodos antes y después
  - `test_relocate_reduces_max_duration` — max(durations) no aumenta
  - `test_swap_conserves_nodes` — mismos nodos antes y después
  - `test_swap_reduces_max_duration` — max(durations) no aumenta

- [ ] **7.7** Test de integración end-to-end — `tests/test_find_routes.py`
  - `test_find_routes_with_mock_routing` — ejecutar el loop completo con mocks de OSM y Google
    - Input: grilla 5×5 de nodos, max_duration=3600s, t_per_tree=120s
    - Mock `f_osm_route_time` → retorna `haversine_m(A, B) * 1.3 / 1.25` (simula camino real)
    - Mock `f_google_route_time` → retorna `haversine_m(A, B) * 1.4 / 1.25`
    - Verificar: retorna > 0 rutas, todos los 25 nodos están cubiertos, ningún nodo repetido
  - `test_find_routes_convergence` — verificar que el loop termina (no infinite loop)
  - `test_find_routes_n_routes_increases` — con max_duration muy corto, n_routes debe crecer
  - `test_find_routes_single_node` — edge case con 1 solo nodo

- [ ] **7.8** Test de comparación P0 vs V3
  - Ejecutar el pipeline P0 (recursive_split + closed TSP) y V3 sobre el mismo dataset
  - Comparar métricas: `max(total_minutes)`, `std(total_minutes)`, número de rutas
  - Este no es un test automatizado de pass/fail, sino un script de benchmark en `tests/benchmark_p0_vs_v3.py`

### Criterios de aceptación

1. Todos los tests unitarios (7.2–7.6) pasan con `pytest`
2. El test de integración (7.7) completa sin errores
3. Cobertura ≥ 80% en los módulos nuevos (`optimize.py`, `routing.py`, nuevas funciones en `utils.py`, `graph.py`, `cluster.py`)
4. El benchmark P0 vs V3 demuestra que V3 produce rutas con menor `max(total_minutes)` en al menos 3 de 5 datasets de prueba

### Riesgos

- **Bajo**: Los mocks de OSM/Google pueden no capturar todos los edge cases de las APIs reales. Mitigación: complementar con tests manuales contra las APIs reales una vez desplegado.

---

## Execution Order

La migración debe implementarse en el siguiente orden, diseñado para maximizar la verificabilidad incremental y permitir paralelismo donde es posible.

### Step 1: Phase 1 (Open-Path TSP)

Implementar primero porque es la base algorítmica de todo lo demás. No tiene dependencias externas. Permite verificar inmediatamente que las rutas son caminos abiertos.

**Resultado verificable:** Ejecutar el pipeline P0 existente con las funciones open-path y confirmar que `route_meters` disminuye (ya no se cuenta la arista de cierre).

Durante esta etapa, el flag `--v3` aún no tiene efecto funcional, pero debe mantenerse como feature flag para habilitar progresivamente las fases siguientes sin afectar el comportamiento legacy.

### Step 2: Phases 2, 3, 4 (en paralelo)

Estas tres fases son independientes entre sí:

- **Phase 2 (Sparse Graph)** — Solo requiere Phase 1 para las funciones TSP que operan sobre el grafo sparse.
- **Phase 3 (Balanced Clustering)** — Totalmente independiente. Puede instalarse y testearse con el pipeline P0.
- **Phase 4 (Routing Clients)** — Totalmente independiente. Se testea con mocks. No necesita nada de las otras fases.

Si se trabaja en serie, el orden recomendado es: **Phase 2 → Phase 3 → Phase 4** (de menor a mayor riesgo).

### Step 3: Phase 5 (Inter-Route Optimization)

Requiere que Phases 1 y 2 estén completas (usa open-path TSP y sparse graph). Implementar los operadores relocate y swap y verificar con tests unitarios antes de integrar.

### Step 4: Phase 6 (V3 Orchestrator)

Wire-up final. Requiere que todas las fases anteriores estén completas. Implementar `find_routes` (V3) y el subcomando `route` del CLI. Verificar ejecutando el pipeline completo con un dataset real.
En este punto, el flag `--v3` debe activar completamente el nuevo pipeline end-to-end.

### Step 5: Phase 7 (Testing)

Los tests deben escribirse incrementalmente junto con cada fase. Sin embargo, el test de integración end-to-end (7.7) y el benchmark P0 vs V3 (7.8) solo pueden ejecutarse una vez que Phase 6 está completa.

### Diagrama de dependencias

```bash
Phase 1
  │
  ├──→ Phase 2 ──┐
  │               │
  │   Phase 3 ───┤
  │               │
  │   Phase 4 ───┤
  │               ↓
  └──→ Phase 5 ──→ Phase 6 ──→ Phase 7
```

### Resumen de nuevas dependencias Python

| Paquete               | Versión mínima | Fase       |
| --------------------- | -------------- | ---------- |
| `scipy`               | ≥1.9           | Phase 2    |
| `numpy`               | ≥1.21          | Phase 2, 3 |
| `scikit-learn`        | ≥1.0           | Phase 3    |
| `k-means-constrained` | ≥0.7.0         | Phase 3    |
| `requests`            | ≥2.28          | Phase 4    |
| `pytest`              | ≥7.0           | Phase 7    |

---

**Última revisión:** 21 de marzo de 2026
