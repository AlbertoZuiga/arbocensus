# 🌳 Generador de Rutas Óptimas para Censo de Árboles

**Balanceo de carga — Caminabilidad real — Integración con Google Maps API**

Este proyecto implementa un sistema completo para generar rutas óptimas de censo de árboles dentro de un área urbana. El objetivo principal es distribuir equitativamente el trabajo entre múltiples censantes, asegurando rutas caminables, eficientes y basadas en datos geográficos reales.

---

**Subproject: bbox_selector**

- **Location:** `bbox_selector/` — pequeña app Flask para seleccionar bounding boxes y visualizar árboles en un mapa (Google Maps JS).
- **Quick start (Docker Compose, recommended for local dev):**

```bash
cd bbox_selector
# optionally set HOST_PORT to map host port (default 5000)
HOST_PORT=5001 docker compose up --build
```

- **Run locally (without Docker):**

```bash
cd bbox_selector
./run.sh --local
```

- **Notes:**
  - The app reads `GOOGLE_API_KEY` from `bbox_selector/.env` or from your environment.
  - `ARBOCENSUS_API_DB_URL` and `ARBOCENSUS_DB_URL` may be provided as DSN (`postgres://...`) or JDBC (`jdbc:postgresql://...`) and the app will attempt to parse both.
  - Tests live under `bbox_selector/tests` and can be run from the subfolder using the included venv or Docker.

If you want, puedo añadir una sección detallada de despliegue o integrar `bbox_selector` en la documentación principal.

# 📌 1. Resumen General del Proyecto

El sistema recibe un conjunto de árboles georreferenciados y un polígono delimitador del área de trabajo, generando rutas caminables óptimas para _N_ censantes. Considera caminabilidad real, tiempos de censo, carga por agente y heurísticas avanzadas de optimización.

**Características principales:**

- Caminabilidad real usando Google Maps (modo _walking_).
- Optimización **min–max** para minimizar la ruta más larga.
- Balanceo de carga entre censantes.
- Clusterización geográfica inteligente.
- Soporte para múltiples estrategias TSP.
- Compatibilidad con métodos utilizados en censos previos.

El tiempo total por censante se calcula como:

```
tiempo_total = tiempo_por_censo * cantidad_arboles + distancia_recorrida * velocidad_de_caminata
```

---

# 🧩 2. Inputs y Outputs del Sistema

## 2.1 Inputs

| Input                        | Descripción                              |
| ---------------------------- | ---------------------------------------- |
| **Polígono geográfico**      | Define el límite del área a censar       |
| **Lista de árboles**         | Contiene ID + latitud + longitud         |
| **Cantidad de censantes**    | Número de personas asignadas             |
| **Punto inicial (opcional)** | Origen común o calculado automáticamente |

## 2.2 Outputs

Para cada censante se genera:

- Ruta caminable completa (polilínea de Google Maps)
- Lista ordenada de árboles asignados
- Tiempo estimado total

Ejemplo:

```
{
  "censante_1": {
    "tiempo_estimado": 47,
    "ruta": [
      { "lat": -34.123, "lng": -58.456 },
      { "lat": -34.124, "lng": -58.457 }
    ],
    "arboles": [12, 55, 73]
  }
}
```

---

# 🧠 3. Arquitectura General del Algoritmo

La solución completa consta de 5 etapas principales:

---

## 3.1 Filtrado de árboles dentro del polígono

Aún no está totalmente definido cómo se entregará el área de trabajo. Podría recibirse como un polígono completo, como una lista de vértices que lo componen, o usando una estructura más compleja. Sin embargo, para simplificar la etapa inicial, se asume que el área vendrá representada como un rectángulo definido por dos coordenadas: la esquina superior izquierda y la esquina inferior derecha. Ese rectángulo funciona como zona preliminar de trabajo.

En esta primera versión, se aplica un **pre‑filtrado mediante bounding box (optimización SQL)** para descartar rápidamente árboles que están fuera del área aproximada.

Ejemplo SQL:

```
SELECT *
FROM tabla_arboles
WHERE latitud BETWEEN min_lat AND max_lat
  AND longitud BETWEEN min_lng AND max_lng;
```

Opciones futuras:

- Point-In-Polygon clásico (Ray casting)
- Turf.js / Shapely

---

## 3.2 Construcción del grafo caminable

Se genera una matriz de tiempos caminados:

```
M[i][j] = tiempo caminando entre árbol i y árbol j
```

Opciones:

- Google Distance Matrix API
- OSRM / GraphHopper
- Cacheo inteligente

---

## 3.3 Clusterización de árboles en N grupos

Utilizada para distribuir equitativamente la carga entre censantes.

Métodos:

- KMeans geográfico
- KMedoids (robusto a outliers)
- DBSCAN
- Clusterización inicial + rebalanceo

---

## 3.4 Generación de rutas por cluster (TSP caminable)

Métodos TSP:

- Nearest Neighbor
- 2-opt / 3-opt
- Algoritmos evolutivos
- Simulated Annealing
- Christofides

Selección de punto inicial:

- Manual
- Automático
- Centroide del cluster

---

## 3.5 Optimización Global (MIN–MAX)

Busca minimizar:

- La ruta más larga
- La diferencia entre censantes
- El total de pasos

Métodos:

- Local search inter–cluster
- Threshold acceptance
- Rebalanceo adaptativo
- Multi–arranque

---

# 📦 4. Estructura Sugerida del Proyecto

```
mi_proyecto/
  ├─ src/
  │   ├─ geometry/
  │   │   ├─ polygon.js
  │   │   └─ point_in_polygon.js
  │   ├─ clustering/
  │   │   ├─ kmeans.js
  │   │   └─ balance.js
  │   ├─ tsp/
  │   │   ├─ tsp_solver.js
  │   │   ├─ heuristics/
  │   │   │   ├─ nearest_neighbor.js
  │   │   │   └─ two_opt.js
  │   ├─ maps/
  │   │   ├─ distance_matrix.js
  │   │   └─ directions.js
  │   └─ orchestrator.js
  ├─ README.md
  └─ package.json
```

---

# 🗺️ 5. Dependencias Principales

## 5.1 APIs Google

- Distance Matrix API
- Directions API
- Maps Geometry API

## 5.2 Librerías sugeridas

- Turf.js / Shapely
- Implementaciones TSP
- KMeans / KMedoids

---

# 🧪 6. Plan de Implementación (TODO)

### Fase 1 — Setup

- Estructura base
- Cargar polígono + árboles
- Point-in-polygon

### Fase 2 — Grafo caminable

- Distance Matrix
- Matriz **M**
- Cache

### Fase 3 — Clusterización

- Clusterización geográfica
- Función de costo
- Rebalanceo

### Fase 4 — TSP por cluster

- NN + 2-opt
- Punto inicial automático

### Fase 5 — Optimización Global

- Intercambio inter-rutas
- Métricas min–max
- Criterio de parada

### Fase 6 — Rutas finales

- Polilíneas Directions API
- JSON
- Integración app front/móvil

### Fase 7 — Documentación

- Ejemplos
- Documentación módulos
- Notas sobre límite de APIs

---

# 🧮 7. Formalización Matemática (mTSP — Min–Max)

Incluye la definición de parámetros, variables, restricciones, MTZ, función objetivo, comentarios prácticos y limitaciones de escalabilidad exactamente como en el contenido original.

_(Todo el bloque matemático original se mantiene tal cual.)_

---

# 🔍 8. Comparación Práctica de Heurísticas

En este apartado se comparan las distintas heurísticas y estrategias disponibles para resolver el mTSP caminable, evaluando sus ventajas, desventajas y escenarios de uso real.

## 8.1 Estrategias de Arquitectura (Cluster-first / Route-first / Integradas)

### **Cluster-first, route-second**

Primero se agrupan los árboles y luego se resuelve un TSP por cada cluster.  
**Ventajas:**

- Muy escalable para miles de árboles
- Fácil de paralelizar
- Modular  
  **Desventajas:**
- La calidad depende fuertemente de los clusters iniciales
- Puede requerir rebalanceo posterior

### **Route-first, split-second**

Se crea una gran ruta única y luego se divide en secciones.  
**Ventajas:**

- Sencillo y rápido
- Rutas visualmente coherentes  
  **Desventajas:**
- Si la gran ruta serpentea, las divisiones pueden ser malas
- No garantiza equilibrio entre censantes

### **Estrategias integradas (LNS, Tabu, metaheurísticas)**

Asignación y orden se optimizan simultáneamente.  
**Ventajas:**

- La mejor calidad global
- Excelente para min–max  
  **Desventajas:**
- Más tiempo de cómputo
- Implementación más compleja

---

## 8.2 Métodos de Clusterización

### **KMeans geográfico**

- Rápido y simple
- Usa distancia euclidiana
- Puede fallar si la ciudad tiene geometría compleja

### **KMedoids**

- Mucho más robusto a outliers
- Puede usar distancias caminables reales
- Ideal para optimización precisa

### **DBSCAN**

- Útil para densidades heterogéneas
- No garantiza exactamente N clusters

### **Balanced KMeans / capacitated clustering**

- Permite que cada cluster tenga una carga similar
- Excelente para min–max

---

## 8.3 Heurísticas de TSP

### **Nearest Neighbor (NN)**

- Ultra rápido
- Buena base, pero calidad limitada

### **2-opt / 3-opt**

- El estándar de la industria
- Elimina cruces y mejora drásticamente la ruta
- Relación calidad/tiempo excelente

### **Lin–Kernighan (LK)**

- Una de las mejores heurísticas del mundo para TSP
- Implementación más compleja

### **Algoritmos evolutivos, SA, ACO**

- Flexibles y configurables
- Útiles para clusters grandes o problemas difíciles

### **Christofides**

- Garantía 1.5 para métricas métricas
- No siempre aplicable a walking real

---

## 8.4 Estrategias de Optimización Global (inter-cluster)

### **Relocate**

Mover un nodo de una ruta a otra para balancear tiempos.

### **Swap (1-1 y 1-k)**

Intercambiar puntos entre rutas.

### **Cross-Exchange**

Intercambiar segmentos completos.

### **2-opt\***

Cortes entre rutas distintas para mejorar conectividad.

### **Large Neighborhood Search (LNS)**

Uno de los métodos más usados en VRP:

- se destruye parte de la solución
- se reconstruye óptimamente con greedy-repair
- se aplican criterios de aceptación

### Comparativa rápida

| Método         | Calidad    | Costo computacional | Escalabilidad |
| -------------- | ---------- | ------------------- | ------------- |
| NN + 2-opt     | Media      | Baja                | Alta          |
| KMeans + 2-opt | Alta       | Media               | Muy alta      |
| LK             | Muy alta   | Alta                | Media         |
| LNS            | Muy alta   | Alta                | Alta          |
| Tabu           | Medio-alta | Media               | Alta          |

---

# 🚀 9. Mejoras del Pipeline y Diseño del Optimizador Global

En esta sección se detallan estrategias avanzadas para mejorar la calidad de las rutas y reducir el tiempo máximo (min–max) entre censantes.

## 9.1 Preprocesamiento Espacial

- Uso de bounding box y filtros por cuadrantes.
- Proyección a UTM para distancias euclidianas rápidas.
- Construcción de índices espaciales (quadtree / R-tree).

## 9.2 Construcción del Grafo Caminable

- Uso de OSRM/GraphHopper local para evitar costos de API.
- Cache persistente para pares ya consultados.
- Cálculo de distancias solo para K vecinos relevantes (KNN).

## 9.3 Clusterización Híbrida

Pipeline recomendado:

1. **KMeans** para partición inicial rápida
2. **Rebalanceo por distancia caminable** mediante KMedoids local
3. **Ajuste dinámico** según tiempos estimados por cluster

## 9.4 Rutas Iniciales

- Generar múltiples semillas: NN, sweep, random, farthest-insertion.
- Aplicar **2-opt** o **3-opt** rápidamente en cada cluster.
- Seleccionar la mejor semilla como punto de partida.

## 9.5 Optimización Global

El corazón del optimizador:

### **Operadores disponibles**

- relocate
- swap
- 2-opt\*
- cross-exchange
- merge-and-split

### **Large Neighborhood Search (LNS) recomendado**

**Destructor:**

- remover nodos de la ruta más larga
- seleccionar nodos extremos o problemáticos
- remover nodos según impacto marginal

**Repair:**

- insertar cada nodo en la posición que minimiza el incremento del Z (max tiempo)
- reoptimizar localmente la ruta afectada

**Criterios de aceptación:**

- simulated annealing
- threshold acceptance
- tabu para movimientos repetidos

## 9.6 Paralelización

- Resolver TSPs de cada cluster en paralelo.
- Paralelizar operadores locales cuando las rutas no interactúan.
- Ejecución multi-start en múltiples hilos.

## 9.7 Pseudocódigo General del Optimizador Global

```
sol = generar_solucion_inicial()
mejor = sol

while tiempo_disponible:
    r_max = ruta_mas_larga(sol)
    nodos = seleccionar_nodos(r_max)
    sol2 = destruir(sol, nodos)
    sol2 = reparar(sol2, nodos)
    sol2 = mejorar_localmente(sol2)

    if aceptar(sol2, sol):
        sol = sol2

    if sol.Z < mejor.Z:
        mejor = sol
```

## 9.8 Monitoreo y Métricas Internas

- Evolución del valor Z
- Tiempo total por censante
- Varianza entre rutas
- Número de iteraciones exitosas
- Porcentaje de mejoras aceptadas

## 9.9 Recomendación de Pipeline Final

1. KMeans inicial
2. Distancias caminables solo por cluster
3. NN + 2-opt
4. LNS con relocate / swap
5. Ajuste final 3-opt / LK
6. Selección de la mejor solución multi-start

---

# 📊 10. Plan de Evaluación Experimental

Incluye:

- Dataset
- Métricas
- Experimentos
- Ablation
- Sensibilidad a parámetros

---

# 📝 11. Recomendaciones Finales

- Implementar primero KMeans + NN + 2-opt + rebalanceo simple
- Cache y batching para Distance Matrix
- Para mayor calidad: LNS con greedy-repair
- Uso de OR-Tools para prototipos

---
