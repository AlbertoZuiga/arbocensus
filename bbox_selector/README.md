# Seleccionar bounding box con Google Maps — `bbox_selector`

Resumen
--------
Pequeña aplicación Flask para seleccionar visualmente un bounding box sobre un mapa (Google Maps JS), y para mostrar los árboles que hay dentro del área visible o dentro del rectángulo dibujado. Las coordenadas del rectángulo se guardan en `saved_bbox.json`. Además la app puede leer directamente de las bases de datos `arbocensus` y `arbocensus-api` (JDBC o DSN) para devolver puntos de árboles vía el endpoint `/trees`.

Rápido: instalación y ejecución (local)
-----------------------------------
1. Preparar la API key de Google Maps JavaScript API:

```bash
export GOOGLE_API_KEY="TU_GOOGLE_MAPS_JS_KEY"
````

2. (Opcional) configurar conexiones a las bases de datos (ver sección siguiente). Si no vas a usar DB directa, la app seguirá funcionando pero no mostrará árboles.

3. Crear entorno, instalar e iniciar:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

4. Abrir en el navegador: `http://127.0.0.1:5000`.

## Qué hace la app

- Muestra un mapa Google Maps con la herramienta de dibujo (rectangle).
- Al dibujar o editar el rectángulo guarda automáticamente sus coordenadas en `saved_bbox.json`.
- Pide al backend `/trees` los árboles dentro del viewport (o los que decidas) y los pinta con un icono de árbol SVG. Al hacer clic sobre un marcador se muestra un InfoWindow con metadatos básicos.

## Conexión directa a bases de datos (JDBC / DSN)

La app puede conectarse directamente a dos fuentes de datos que ya existen en tu entorno:

- `ARBOCENSUS_API_DB_URL`: la base donde está `arbocensus_api_app_sample` (col. `tree_latitude`, `tree_longitude`).
- `ARBOCENSUS_DB_URL`: la base donde está `arbocensus_app_sample` (col. `latitude`, `longitude`).

Formas de proporcionar las URLs/credenciales:

1. DSN/Postgres completo (recomendado — más simple):

```bash
export ARBOCENSUS_API_DB_URL='postgres://user:password@host:5432/arbocensus_api_dev'
export ARBOCENSUS_DB_URL='postgres://user2:password2@host2:5432/arbocensus_main'
```

2. JDBC (si ya tienes `jdbc:postgresql://host:port/dbname` en tu `.env`): la app reconoce `jdbc:postgresql://...` y parsea host/port/dbname. Si la JDBC no incluye user/password, exporta las credenciales por separado:

```bash
export ARBOCENSUS_API_DB_URL='jdbc:postgresql://arbocensus-dev...:5432/arbocensus_api_dev'
export ARBOCENSUS_API_DB_URL_USER='mi_usuario'
export ARBOCENSUS_API_DB_URL_PASSWORD='mi_password'

export ARBOCENSUS_DB_URL='jdbc:postgresql://cdsk218k...:5432/d95dvg1udv7qqn'
export ARBOCENSUS_DB_URL_USER='mi_usuario2'
export ARBOCENSUS_DB_URL_PASSWORD='mi_password2'
```

3. Alternativa: si prefieres no exportar variables, puedes colocar las credenciales en `bbox_selector/.env` (el proyecto ya usa `python-dotenv` para cargar `.env`). Asegúrate de agregar `.env` a `.gitignore`.

## Cómo funciona `/trees` (resumen técnico)

- El endpoint `GET /trees?north=..&south=..&east=..&west=..&max=..` devuelve una lista de puntos `{lat,lng,meta}`.
- El servidor intentará, en este orden, conectarse a:
  1. `ARBOCENSUS_API_DB_URL` y consultar `arbocensus_api_app_sample` (campos `tree_latitude`, `tree_longitude`).
  2. `ARBOCENSUS_DB_URL` y consultar `arbocensus_app_sample` (campos `latitude`, `longitude`).
- Los resultados se combinan y se deduplican por coordenadas (redondeo a 6 decimales).
- Si no hay credenciales/DB accesible, `/trees` devolverá `{ "ok": true, "trees": [] }`.

Nota: las consultas usan filtros `latitude BETWEEN south AND north` y `longitude BETWEEN west AND east`. Si tus tablas tienen columnas/formatos diferentes, dímelo y adaptaré las consultas.

## Cliente: cómo se muestran los árboles

- La UI pide automáticamente `/trees` cuando el mapa está `idle` (tras mover/zoom) y también después de dibujar un rectángulo.
- Cada árbol se muestra con un marcador SVG (ícono de árbol verde) y un `InfoWindow` con metadatos básicos (ID, sample id, etc.).
- Opcional: puedes cambiar el cliente para que pida sólo los árboles dentro del rectángulo dibujado (en vez del viewport). Pídemelo y lo actualizo.

## Rendimiento y escalado

- La app limita por `max` (por defecto 300) para evitar traer millones de puntos.
- Para visualización de muchos puntos, te recomiendo usar clustering (MarkerClusterer) o paginación en el servidor.
- Si tu base tiene PostGIS o índices espaciales, la consulta bbox será mucho más rápida; si no, considera agregar índices sobre las columnas `latitude`/`longitude`.

## Seguridad y buenas prácticas

- No subas credenciales ni `.env` al repositorio. Añade a `.gitignore`:

```
.venv
.env
saved_bbox.json
secrets/
```

- Restringe la `GOOGLE_API_KEY` por referer en la consola de Google Cloud (evita uso público indiscriminado).
- Si expones la app, añade autenticación o coloca el servicio detrás de una VPN/restricción de red.

## Pruebas rápidas y uso de ejemplo

- Ejecutar servidor y probar endpoint `/trees` con curl (ejemplo):

```bash
curl "http://127.0.0.1:5000/trees?north=-33.3&south=-33.6&east=-70.4&west=-70.8&max=200"
```

- Dibujar rectángulo en la UI y verificar que `saved_bbox.json` se crea/actualiza.

## Siguientes mejoras recomendadas

- Añadir clustering de marcadores en cliente para grandes densidades.
- Cambiar cliente para usar únicamente rectángulo dibujado (si prefieres esa lógica).
- Añadir paginación/sampling en SQL para resultados grandes.
- Añadir tests unitarios (pytest) que simulen conexiones a DB y comprueben `/trees`.

## Contacto / notas finales

Si quieres que adapte las consultas SQL a columnas diferentes o que implemente clustering o petición sólo dentro del rectángulo, dime cuál prefieres y lo hago.

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
