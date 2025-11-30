# Generador de Rutas Óptimas para Censo de Árboles — TODO (Sprint 48h)

## 🎯 Objetivo del Sprint
Implementar un **pipeline mínimo funcional**, modular y encadenado por etapas, que:
1. Reciba un JSON exportado desde `bbox_selector`.
2. Procese árboles y área en etapas separadas (cada una en su propio directorio).
3. Genere rutas iniciales usando **Vecino Más Cercano (NN) + 2-opt**.
4. Use **distancia euclidiana** para rapidez (decisión sobre distancia caminable queda documentada).

---

## 🗓 Roadmap Rápido

### **Día 1**
- Crear estructura de directorios por etapas.
- Implementar:
  - `01_bbox_input`
  - `02_filter`
  - `03_graph` (matriz de distancias euclidianas)
- Documentar decisión sobre métrica de distancia.

### **Día 2**
- Implementar:
  - `04_cluster` (opcional en MVP)
  - `05_tsp` (NN + 2-opt)
  - `06_output`
- Crear script `run.py` para ejecutar todo el pipeline.
- Validar con JSON real de `bbox_selector`.

---

## 🧩 Tareas por Etapa (encadenadas)

---

### **P0 — Esqueleto del Proyecto**
**Descripción:** Crear estructura modular de stages y un runner que ejecute etapas secuenciales.  
**Directorio:** raíz  
**Archivos:** `run.py`, carpetas `stages/01..06/`, `examples/`  
**Criterios:**  
- `run.py --list` muestra etapas.  
- Cada etapa se ejecuta llamando funciones/archivos internos.

---

### **P0 — Etapa 01: Ingesta desde bbox_selector**
**Input:** archivo JSON exportado desde `bbox_selector`  
**Output:** `stages/01_bbox_input/01_input.json`  
**Archivo:** `stages/01_bbox_input/load_input.py`  
**Criterios:**  
- Validación de estructura (`polygon`, `trees`, `id`, `lat`, `lng`).  
- JSON normalizado.

---

### **P0 — Etapa 02: Filtrado**
**Input:** `01_input.json`  
**Output:** `02_filtered.json`  
**Archivo:** `filter.py`  
**Filtro mínimo:**  
- Árboles duplicados  
- Faltantes de coordenadas  
- Opcional: verificar dentro del polígono  
**Criterios:** salida válida y ≤ entrada.

---

### **P0 — Etapa 03: Grafo / Matriz de Distancias**
**Input:** `02_filtered.json`  
**Output:** `03_graph.json`  
**Archivo:** `build_graph.py`  
**Criterios:**  
- Matriz NxN simétrica de distancias euclidianas.  
- Tiempo razonable (<1s para <1000 nodos).  

---

### **P0 — Etapa 04: Clustering**
**Input:** `03_graph.json`  
**Output:** `04_clusters.json`  
**Archivo:** `cluster.py`  
**Criterios:**  
- Si no se usa clustering, generar un único cluster.  

---

### **P0 — Etapa 05: TSP (NN + 2-opt)**
**Input:**  
- `03_graph.json`  
- o `04_clusters.json` si aplica  
**Output:** `05_routes.json`  
**Archivos:** `tsp.py`, `two_opt.py`  
**Criterios:**  
- Cada cluster produce una ruta válida sin repeticiones.  
- 2-opt no debe empeorar la ruta.

---

### **P0 — Etapa 06: Output Final**
**Input:** `05_routes.json` + nodos  
**Output:**  
- `routes_final.json`  
- `routes_final.geojson`  
**Archivo:** `format_output.py`  
**Criterios:**  
- GeoJSON válido con coordenadas ordenadas por ruta.  

---

### **P1 — Decisión de Métrica de Distancia**
**Archivo:** `docs/decision/DECISION_distance_metric.md`  
**Debe incluir:**  
- Euclidiana (actual)  
- OSRM/Valhalla  
- Google Distance Matrix  
**Criterios:** documento claro + plan futuro.

---

### **P1 — Ejemplo Reproducible**
**Files:**  
- `examples/example_bbox.json`  
- Instrucciones rápidas en README  
**Criterios:** pipeline completo debe correr con este ejemplo.

---

## 📁 Estructura Final del Proyecto

```
stages/
  01_bbox_input/
    load_input.py
  02_filter/
    filter.py
  03_graph/
    build_graph.py
  04_cluster/
    cluster.py
  05_tsp/
    tsp.py
    two_opt.py
  06_output/
    format_output.py
examples/
  example_bbox.json
run.py
TODO.md
```

---

## 🧪 Comandos Útiles

```
python run.py --input examples/example_bbox.json --out stages/06_output/

python stages/03_graph/build_graph.py stages/02_filter/trees_filtered.json stages/03_graph/graph.json

python stages/05_tsp/tsp.py stages/03_graph/graph.json stages/05_tsp/routes.json
```

---

## ✔️ Checklist Final (Sprint Cerrado)

- [ ] Pipeline completo ejecutándose de etapa en etapa.  
- [ ] Cada etapa entrega JSON válido a la siguiente.  
- [ ] `routes_final.geojson` generado correctamente.  
- [ ] Ejemplo desde `bbox_selector` funcionando.  
- [ ] Documento de decisión sobre métrica de distancia incluido.

