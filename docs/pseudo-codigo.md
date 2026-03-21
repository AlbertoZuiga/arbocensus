# Pseudocódigo

## V_0

```python
def find_routes(locations, max_duration, f_duration, delta):
    n_routes = estimate_quantity(locations, max_duration)
    clusters = knn(locations, n_routes)
    durations = []
    for c in clusters:
        d = cluster_duration(c, f_duration)
        durations.append(d)
    diff = durations - max_duration
    max_diff = max(math.abs(diff))
    if max_diff/max_duration < delta:
        return clusters
    sum_diff = sum(diff)

    if abs(sum_diff) <= delta * max_duration * n_routes:
        # Recalcular con mismo n_routes
    elif sum_diff > 0:
        n_routes += 1
        # volver a calcular clusters
    else:
        n_routes -= 1
        # volver a calcular clusters
```

## V_1

```python
def find_optimal_routes(locations, max_duration_per_route, f_tsp, tolerance=0.1):
    # 1. Estimación inicial inteligente (basada en tiempo total estimado / tiempo max)
    # Calculamos un TSP gigante rápido para estimar la longitud total del grafo
    total_time_estimate = estimate_total_workload(locations)
    n_routes = math.ceil(total_time_estimate / max_duration_per_route)
    
    # Evitamos bucles infinitos
    max_iterations = 10
    best_solution = None
    min_error = float('inf')

    for i in range(max_iterations):
        # 2. Usar K-Means Constrained (garantiza balanceo de nodos desde el inicio)
        # target_size se calcula dinámicamente según el N actual
        clusters = k_means_constrained(locations, n_clusters=n_routes)
        
        # 3. Calcular duración real (TSP) de cada cluster
        durations = []
        for c in clusters:
            # f_tsp calcula el tiempo real de ruta + servicio
            d = f_tsp(c) 
            durations.append(d)
        
        # 4. Análisis de desviaciones
        max_route_time = max(durations)
        avg_route_time = sum(durations) / n_routes
        
        # Diferencia porcentual respecto al máximo permitido
        deviation = (max_route_time - max_duration_per_route) / max_duration_per_route

        # Guardamos la mejor solución encontrada hasta ahora por si no logramos la perfecta
        if deviation < min_error:
            min_error = deviation
            best_solution = clusters

        # 5. Lógica de Control (Decision Tree)
        
        # CASO A: Éxito (estamos dentro del margen de tolerancia)
        if deviation <= tolerance:
            return clusters
        
        # CASO B: El promedio está bien, pero el máximo se pasa.
        # Significa que hay clusters muy desiguales (uno gigante, uno pequeño).
        # K-Means Constrained ayuda, pero si persiste, necesitamos MÁS rutas para diluir.
        elif avg_route_time <= max_duration_per_route * (1 - tolerance):
             # Estamos holgados en promedio, pero un outlier rompe la regla.
             # Intentamos re-balancear moviendo puntos (Swap) o subimos N ligeramente.
             # Para simplificar:
             n_routes += 1
             
        # CASO C: Incluso el promedio se pasa del tiempo máximo.
        # Físicamente imposible cumplir con este N.
        else:
            # Estimamos cuánto nos falta: si el promedio es 120% del max, subimos un 20% N.
            factor = avg_route_time / max_duration_per_route
            add_routes = math.ceil(n_routes * (factor - 1))
            n_routes += max(1, add_routes) # Asegurar que sumamos al menos 1

    # Si se agotan las iteraciones, devolvemos lo mejor que encontramos
    print("Warning: No convergió perfectamente, devolviendo mejor aproximación")
    return best_solution
```

## V_2

```python
# Usa tres niveles de precisión:
#   1) Distancia euclidiana (barata)
#   2) Routing con OpenStreetMap (aproximación realista)
#   3) Validación final con Google API (solo para rutas consolidadas)

def find_routes_v2(
    locations,
    max_duration_per_route,
    f_google_route_time,
    f_osm_route_time,
    tolerance=0.1,
    k_neighbors=10,
    max_iterations=12
):

    # -------------------------------------------------
    # 0. Inicialización
    # -------------------------------------------------

    # Cache para evitar repetir llamadas a Google
    google_cache = {}

    # Cache opcional para OSM
    osm_cache = {}

    best_solution = None
    best_error = inf

    # -------------------------------------------------
    # 1. Estimación inicial barata (EUCLIDIANA)
    # -------------------------------------------------
    # NO usa APIs externas

    total_euclidean_distance = estimate_euclidean_tsp(locations)

    walking_speed = 4.5  # km/h aproximado
    total_time_estimate = total_euclidean_distance / walking_speed

    n_routes = ceil(total_time_estimate / max_duration_per_route)

    # -------------------------------------------------
    # 2. Construcción de grafo sparse
    # -------------------------------------------------

    sparse_graph = build_sparse_graph(
        locations,
        k_neighbors
    )

    # -------------------------------------------------
    # 3. Bucle principal de optimización
    # -------------------------------------------------

    for iteration in range(max_iterations):

        # ---------------------------------------------
        # 3.1 Clustering espacial inicial
        # ---------------------------------------------

        clusters = k_means_constrained(locations, n_clusters=n_routes)

        routes = []
        route_durations = []

        # ---------------------------------------------
        # 3.2 Generación de rutas por cluster
        # ---------------------------------------------

        for cluster in clusters:

            # -----------------------------
            # Ruta inicial heurística
            # -----------------------------

            route = nearest_neighbor_route(cluster, sparse_graph)

            # -----------------------------
            # Optimización local
            # -----------------------------

            route = two_opt(route, sparse_graph)

            # -------------------------------------------------
            # 3.3 Evaluación con OpenStreetMap (APROXIMACIÓN)
            # -------------------------------------------------
            # Aquí se usa un motor basado en OSM
            # Ejemplos posibles: OSRM / GraphHopper / OSMnx

            duration_osm = compute_route_time_with_cache(
                route,
                f_osm_route_time,
                osm_cache
            )

            routes.append(route)
            route_durations.append(duration_osm)

        # ---------------------------------------------
        # 3.4 Evaluación global
        # ---------------------------------------------

        max_route_time = max(route_durations)
        avg_route_time = mean(route_durations)

        deviation = (max_route_time - max_duration_per_route) / max_duration_per_route

        if deviation < best_error:
            best_error = deviation
            best_solution = routes

        # ---------------------------------------------
        # 3.5 Criterio de parada
        # ---------------------------------------------

        if deviation <= tolerance:
            break

        # ---------------------------------------------
        # 3.6 Balanceo de clusters
        # ---------------------------------------------

        clusters = relocate_nodes_between_clusters(
            clusters,
            route_durations,
            max_duration_per_route
        )

        # ---------------------------------------------
        # 3.7 Ajuste del número de rutas
        # ---------------------------------------------

        if avg_route_time > max_duration_per_route:

            factor = avg_route_time / max_duration_per_route
            add_routes = ceil(n_routes * (factor - 1))
            n_routes += max(1, add_routes)

        else:

            n_routes += 1

    # -------------------------------------------------
    # 4. VALIDACIÓN FINAL CON GOOGLE API
    # -------------------------------------------------
    # Solo se evalúan las rutas finales para minimizar costos

    validated_routes = []

    for route in best_solution:

        duration_google = compute_route_time_with_cache(
            route,
            f_google_route_time,
            google_cache
        )

        validated_routes.append((route, duration_google))

    # -------------------------------------------------
    # 5. Resultado final
    # -------------------------------------------------

    return validated_routes


# -----------------------------------------------------
# Función auxiliar con cache (sirve para OSM y Google)
# -----------------------------------------------------

def compute_route_time_with_cache(route, f_route_time, cache):

    total = 0

    for i in range(len(route) - 1):

        A = route[i]
        B = route[i + 1]

        key = (A, B)

        if key not in cache:
            cache[key] = f_route_time(A, B)

        total += cache[key]

    return total
```

## V_3

```python
import math

def find_routes(
    locations,
    expected_duration_per_route,
    t_per_tree,
    f_google_route_time,
    f_osm_route_time,
    lower_factor=0.90,
    upper_factor=1.10,
    k_neighbors=12,
    max_iterations=14,
    hysteresis_rounds=2,
    hard_max_duration=None,
):

    # -------------------------------------------------
    # 0. Inicialización
    # -------------------------------------------------
    google_cache = {}
    osm_cache = {}

    lower_bound = expected_duration_per_route * lower_factor
    upper_bound = expected_duration_per_route * upper_factor

    # Si existe un límite duro externo, se aplica aquí
    if hard_max_duration is None:
        hard_upper_limit = upper_bound
    else:
        hard_upper_limit = hard_max_duration

    best_feasible_solution = None
    best_feasible_score = float('inf')

    # Mejor solución global (aunque no sea factible)
    best_overall_solution = None
    best_overall_gap = float('inf')

    # Para evitar oscilación de n_routes
    over_counter = 0
    under_counter = 0
    last_direction = 0   # +1 subimos rutas, -1 bajamos rutas, 0 sin cambio

    # -------------------------------------------------
    # 1. Estimación inicial de número de rutas
    # -------------------------------------------------
    walking_speed = 4.0
    total_euclidean_distance = estimate_euclidean_tsp(locations)
    travel_time_estimate = total_euclidean_distance / walking_speed
    service_time_estimate = len(locations) * t_per_tree
    total_time_estimate = travel_time_estimate + service_time_estimate

    n_routes = max(1, math.ceil(total_time_estimate / expected_duration_per_route))

    # -------------------------------------------------
    # 2. Estructuras de vecindad
    # -------------------------------------------------
    kd_tree = build_kd_tree(locations)
    sparse_graph = build_sparse_graph_from_kdtree(locations, kd_tree, k_neighbors)

    # -------------------------------------------------
    # 3. Loop principal
    # -------------------------------------------------
    for iteration in range(max_iterations):

        # 3.1 Clustering (warm start opcional en implementación real)
        clusters = k_means_constrained(locations, n_clusters=n_routes)

        routes = []
        durations = []

        # 3.2 Construcción y mejora de rutas abiertas
        for cluster in clusters:
            route = nearest_neighbor_open_path(cluster, sparse_graph)
            route = two_opt_open_path(route, sparse_graph)

            duration = compute_open_route_time_with_cache(
                route, f_osm_route_time, osm_cache, t_per_tree
            )
            routes.append(route)
            durations.append(duration)

        # 3.3 Ajustes inter-ruta
        routes = relocate_nodes_between_routes(
            routes, durations, sparse_graph, upper_bound
        )
        routes = swap_nodes_between_routes(
            routes, durations, sparse_graph, upper_bound
        )

        # 3.4 Recalcular duraciones después de ajustes
        durations = []
        for route in routes:
            duration = compute_open_route_time_with_cache(
                route, f_osm_route_time, osm_cache, t_per_tree
            )
            durations.append(duration)

        # 3.5 Métricas
        max_route = max(durations)
        min_route = min(durations)
        avg_route = mean(durations)
        spread = max_route - min_route

        # Gap total a la banda: 0 significa que ya estamos dentro
        over_gap = max(0, max_route - upper_bound)
        under_gap = max(0, lower_bound - min_route)
        band_gap = over_gap + under_gap

        # Score factible: prioriza balance cuando la solución ya cumple banda
        feasible_score = avg_route + 0.25 * spread

        # Guardar mejor global
        if band_gap < best_overall_gap:
            best_overall_gap = band_gap
            best_overall_solution = routes

        # Guardar mejor factible (dentro de banda y sin romper límite duro)
        feasible = (
            (max_route <= upper_bound) and
            (min_route >= lower_bound) and
            (max_route <= hard_upper_limit)
        )

        if feasible and feasible_score < best_feasible_score:
            best_feasible_score = feasible_score
            best_feasible_solution = routes

        # 3.6 Criterio de convergencia
        if feasible:
            break

        # 3.7 Histéresis para evitar ping-pong de n_routes
        if max_route > upper_bound:
            over_counter += 1
            under_counter = 0
        elif min_route < lower_bound:
            under_counter += 1
            over_counter = 0
        else:
            over_counter = 0
            under_counter = 0

        change_direction = 0

        # Exceso sostenido: agregar rutas
        if over_counter >= hysteresis_rounds:
            if avg_route > upper_bound:
                factor = avg_route / expected_duration_per_route
                delta_n = max(1, math.ceil(n_routes * (factor - 1)))
            else:
                delta_n = 1
            n_routes += delta_n
            change_direction = +1
            over_counter = 0

        # Defecto sostenido: quitar rutas
        elif under_counter >= hysteresis_rounds:
            delta_n = 1
            n_routes = max(1, n_routes - delta_n)
            change_direction = -1
            under_counter = 0

        # Si no cumplió umbral de histéresis, no se cambia n_routes

        # Regla de amortiguación: si intenta cambiar al sentido opuesto,
        # exigimos una iteración extra de evidencia
        if change_direction != 0 and (last_direction * change_direction < 0):
            if change_direction > 0:
                over_counter = 1
            else:
                under_counter = 1

        if change_direction != 0:
            last_direction = change_direction

    # -------------------------------------------------
    # 4. Selección final
    # -------------------------------------------------
    final_routes = best_feasible_solution if best_feasible_solution is not None else best_overall_solution

    # -------------------------------------------------
    # 5. Validación final con Google API
    # -------------------------------------------------
    validated = []
    for route in final_routes:
        duration_google = compute_open_route_time_with_cache(
            route, f_google_route_time, google_cache, t_per_tree
        )
        validated.append((route, duration_google))

    return validated

# -----------------------------------------------------
# Función auxiliar de evaluación de tiempo
# -----------------------------------------------------
def compute_open_route_time_with_cache(route, f_route_time, cache, t_per_tree):
    total_travel_time = 0

    # Iteramos solo hasta el penúltimo nodo (ruta abierta)
    for i in range(len(route) - 1):
        A = route[i]
        B = route[i + 1]
        key = (A, B)

        if key not in cache:
            cache[key] = f_route_time(A, B)

        total_travel_time += cache[key]

    # Tiempo constante por arbol multiplicado por el total de árboles en la ruta
    total_service_time = len(route) * t_per_tree

    return total_travel_time + total_service_time
```
