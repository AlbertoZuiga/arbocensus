Redacta o actualiza una sección de la tesis en docs/thesis/main.tex.

Argumento: $ARGUMENTS
Ejemplos: /thesis-section resumen · /thesis-section §1.1 · /thesis-section §2.3.4

---

## Pasos obligatorios

1. Lee `docs/thesis/main.tex` para encontrar la sección y ver el contenido actual.
2. Lee `DEVELOPMENT_PLAN.md` — fuente de verdad técnica (arquitectura, decisiones, código).
3. Lee `docs/PROBLEM_STATEMENT.md` — notación formal del problema (ecuaciones, restricciones).
4. Si el usuario pasó información adicional en el mensaje (datos, métricas, citas, cambios), incorporarla.
5. Redacta el borrador siguiendo las reglas de abajo.
6. Reemplaza el bloque `% TODO` correspondiente en main.tex con el contenido generado.
7. Deja un comentario `% DRAFT — revisar` al inicio del bloque redactado.

---

## Reglas de escritura (NO negociables)

- **Idioma**: español académico, TERCERA PERSONA. ✓ "se desarrolló" ✗ "desarrollé" ✗ "básicamente"
- **Citas**: Harvard. `\citep{key}` → (Autor, año). `\citet{key}` → Autor (año). Claves solo de `bibliography.bib`.
- **LaTeX**: escapar `%`→`\%`, `$`→`\$`, `_`→`\_`. Código/identifiers: `\texttt{}`. Términos técnicos en inglés: `\textit{}`.
- **No inventar datos**: si la sección requiere métricas reales (§3.x), dejar `[DATO PENDIENTE]` con nota de qué medir.
- **Extensión**: ajustarse a la indicada por sección; no inflar con padding.

---

## Hechos técnicos inamovibles

| Hecho | Valor |
|-------|-------|
| T\_max | Restricción **dura** (AddDimension capacity) |
| T\_min | Restricción **blanda** (penalización 10 000, SetCumulVarSoftLowerBound) |
| Dummy depot | Nodo 0; nodos reales 1..n; extracción: `IndexToNode(i) - 1` |
| k (nº rutas) | Determinado **automáticamente** por OR-Tools — nunca input manual |
| Distancias | Red peatonal OSM via OSRM — NO Google Maps, NO euclidianas |
| Caché matriz | SHA-256 de IDs de árboles activos ordenados |
| Orden de visita | `RouteStop.sequence` — no hay campo `tree_sequence` en Route |
| T\_min / T\_max por defecto | 7 200 s / 10 800 s (configurables) |
| Costo fijo vehículo | 100 000 s |
| Tiempo límite solver | 180 s por defecto |
| Coordenadas OSRM | lon,lat en URL (no lat,lon) |

---

## Qué cubrir por sección

### resumen
300 palabras, máx 1 página. 4 párrafos: (1) problema, (2) método (Open mTSP, OR-Tools, OSRM),
(3) resultados `[DATO PENDIENTE]`, (4) conclusión/aporte.
NO mencionar Django, React, Celery.

### §1.1 — Descripción de la Problemática (~400 palabras)
Censo de árboles urbanos: escala, complejidad logística, planificación manual fallida.
Restricciones operacionales reales: jornada acotada, rutas abiertas, k desconocido.
NO describir la solución.

### §1.2 — Estado Actual del Problema (~500 palabras)
Herramientas actuales (GIS genérico, planificación manual). Literatura: mTSP
\citep{bektas2006multiple}, \citep{laporte1992traveling}; VRPTW \citep{solomon1987algorithms},
\citep{toth2014vehicle}; GLS \citep{voudouris1999guided}.
Qué falta: ventanas globales por ruta, rutas abiertas, k automático, red real.

### §1.3 — Solución Planteada (~400 palabras)
Qué es Arbocensus y qué resuelve. Actores: Administrador y Censador.
Flujo alto nivel: CSV → PostGIS → OSRM → OR-Tools → Leaflet.
Diferenciadores: k automático, T_min blanda, distancias reales.
NO entrar en detalles de implementación.

### §2.1 — Arquitectura del Sistema (~500 palabras + Figura arquitectura)
Monolito modular Django. 5 capas: presentación / API / lógica / datos / routing.
Justificar: sin microservicios (equipo unipersonal), Celery (solver tarda minutos),
OSRM local (sin costos API). Flujo de datos en proceso de optimización.

### §2.2 — Modelo de Datos (~500 palabras + diagrama ER simplificado)
9 entidades con relaciones. Decisiones: SHA-256 caché, RouteStop fuente de verdad,
UUID PKs, PointField SRID=4326, estados del OptimizationJob.

### §2.3.1 — Formulación del Problema (~400 palabras + ecuaciones)
Formalizar con notación de PROBLEM_STATEMENT.md. Ecuaciones T_r y restricciones.
Identificar como Open mTSP con ventanas globales por ruta. Diferencia de VRPTW clásico.

### §2.3.2 — Construcción de la Matriz de Costos (~350 palabras)
OSRM /table/v1/foot, orden lon,lat, null→9 999 999. Caché SHA-256 y su lógica de
invalidación. Escala (≤400 puntos, --max-table-size 5000, sin chunking en MVP).

### §2.3.3 — Estimación del Número de Rutas (~300 palabras + ecuación N_max)
Por qué NO iteración externa. N_max = ⌈(n·s + (n-1)·c̄) / T_min⌉ + 5.
Fixed vehicle cost 100 000 para minimización interna.

### §2.3.4 — Solver VRP con OR-Tools (~500 palabras)
4 bloques: (1) dummy depot, (2) dimensión temporal (T_max hard, T_min soft + justificación),
(3) minimización rutas + balance, (4) búsqueda (GLS + PATH_CHEAPEST_ARC, 180 s).
Fallo informativo si solution is None.

### §2.4 — API REST (~400 palabras + tabla de endpoints)
DRF, JWT, roles Admin/Surveyor. Tabla 4 grupos: auth, datasets, optimization, routes.
GeoJSON para árboles y rutas. Polling de OptimizationJob.

### §2.5 — Interfaz de Usuario (~400 palabras)
Stack: React 18 + Vite, Zustand, React Query, shadcn/ui, Leaflet.
Flujo Admin (5 pasos): login→CSV→mapa árboles→configurar+lanzar→polling→rutas coloreadas.
Portal censador = V2, no implementado en MVP.

### §3.1.1 — Métricas de Calidad de Rutas (~300 palabras + Tabla metricas)
Dataset real: N árboles, zona, parámetros usados. k rutas, tiempo cómputo.
Tabla: T_r promedio, std dev, std/promedio (criterio <15%), rutas que violan T_max (=0),
cobertura total. Si no hay datos aún: estructura de tabla con `[DATO PENDIENTE]`.

### §3.1.2 — Comparación con Solución Greedy (~350 palabras + tabla comparativa)
Baseline: nearest neighbor, mismo dataset, mismo T_min/T_max, generado programáticamente.
Tabla comparativa: k, tiempo total desplazamiento, std dev tiempos, violaciones T_max.
Si no hay datos: estructura con `[DATO PENDIENTE]`.

### §3.2 — Posibles Mejoras (~300 palabras)
5 mejoras V2 con justificación: portal censador, GeoJSON/legacy DB import,
chunking OSRM >500 pts, análisis sensibilidad solver, Playwright E2E.
