# Auditoría de objetivo + post-pass de re-secuenciado + nuevos brazos de configuración

**Fecha:** 2026-07-18
**Datos:** `objective-audit-postpass-sweep-20260718.csv` (toda cifra de este reporte sale de ese CSV o del reporte de auditoría de objetivo).

Todo el barrido corre por *overrides* de CLI. La configuración de producción del solver no cambia:
defaults (`spatial_term`, `PenaltyConfig` actual, `SPATIAL_SPAN_COEF=3`) intactos.

---

## Registro previo (fijado ANTES de correr — no renegociable a posteriori)

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s (2 min) |
| T_max | 10 800 s (3 h) |
| T_min | 7 200 s (2 h, default de producción) |
| Límite de tiempo del solver | heurístico `min(30 + 1.5·n, 120)` s |
| Semillas | 3 por celda |

### Instancias

Batería `{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales `{157, 72, 43}` y `n=1607`.

---

## Fase 1 — Auditoría del objetivo

### Pregunta de investigación

¿Los vehículos **vacíos** (buffer +5 en `estimate_max_vehicles`) pagan la penalización
`soft lower bound` sobre el `end cumul` de la dimensión Time? Si end\_cumul = 0 < T\_min,
la violación es T\_min × SOFT\_LOWER\_PENALTY = 7 200 × 10 000 = **72 000 000** por vehículo.

### Metodología

Comando `manage.py objective_audit --dataset reference-n1607 --balance-arm actual`.
Reconstrucción manual del objetivo por término:

| Término | Fórmula |
| --- | --- |
| arc\_cost | Σ `time_end_cumul[v]` (callback de costo = callback Time) |
| fixed\_cost | k\_activos × 100 000 |
| soft\_lower | Σ max(0, T\_min\_eff − end\_T[v]) × 10 000 |
| soft\_upper | Σ max(0, end\_T[v] − upper\_target) × 500 |
| drop\_cost | n\_drops × 1 000 000 |
| span\_cost | span\_coef × Σ `dist_end_cumul[v]` |

Comparación `objective()` de OR-Tools vs suma manual. Resultado esperado: delta ≈ 0
(diferencia solo por redondeo de ceiling).

### Resultados

Salidas completas versionadas: `objective-audit-20260718-reference-n1607.txt` y
`objective-audit-20260718-area-26-n157.txt`. El comando se ajustó antes de correr para
desglosar `soft_lower` entre vehículos activos y vacíos y basar el veredicto en el delta
contra `ObjectiveValue()` (no en la mera existencia de vehículos vacíos).

#### Descomposición por término

| Término | reference-n1607 | area-26-n157 |
| --- | ---: | ---: |
| arc\_cost (Time cumul) | 254 050 | 23 871 |
| fixed\_vehicle\_cost | 2 500 000 | 300 000 |
| soft\_lower (activos) | 0 | 0 |
| soft\_lower (vacíos, si pagaran) | 792 000 000 | 360 000 000 |
| soft\_upper | 14 526 000 | 0 |
| drop\_cost | 0 | 0 |
| span\_cost (Distance) | 205 587 | 14 013 |
| **Manual (con vacíos)** | **809 485 637** | **360 337 884** |
| **`ObjectiveValue()` OR-Tools** | **17 485 637** | **337 884** |
| delta (OR-Tools − manual) | −792 000 000 | −360 000 000 |
| delta excluyendo vacíos | **0** | **0** |

Solución n=1607: k\_activos = 25, k\_vacíos = 11, max\_vehicles = 36, drops = 0,
rutas de 21 a 80 árboles. Área chica: k\_activos = 3, k\_vacíos = 5, max\_vehicles = 8.

#### Verificación

El delta crudo es exactamente −(k\_vacíos × T\_min × SOFT\_LOWER\_PENALTY):
−11 × 72 000 000 = −792 000 000 en n=1607 y −5 × 72 000 000 = −360 000 000 en el
área chica. Al excluir el cargo de los vacíos, la reconstrucción manual coincide con
`ObjectiveValue()` con **delta = 0 exacto** en ambas instancias (ni siquiera hay residuo
de redondeo: el callback ya entrega enteros con ceiling).

#### Veredicto — vehículos vacíos

**NO PAGAN.** OR-Tools omite del objetivo los costos de vehículos no usados: un vehículo
con end\_cumul = 0 no aporta soft lower bound (ni fixed cost). El buffer +5 de
`estimate_max_vehicles` es inocuo para el objetivo: no existe la "fuerza oculta" de
72 000 000 por vehículo vacío, y por eso el solver puede dejar 11 de 36 vehículos vacíos
(k = 25) sin castigo alguno. Esto explica el registro histórico k = 25 con buffer amplio.

Consecuencias:

- k **no** está distorsionado por el buffer; cualquier recalibración de penalizaciones
  basada en descontar o neutralizar el cargo de vehículos vacíos queda **descartada como
  trabajo futuro** — el cargo no existe.
- La presión de relleno hasta T\_min proviene únicamente del soft lower de los vehículos
  **activos** (aquí 0: todas las rutas activas superan T\_min), no de los vacíos.
- En n=1607 el término dominante del objetivo real es soft\_upper (14,5 M de 17,5 M,
  83 %): el solver está pagando por rutas sobre el target de 9 000 s, coherente con el
  régimen saturado ya documentado.

---

## Fase 2 — Post-pass de re-secuenciado intra-ruta

### Descripción

Tras extraer rutas del solver, se aplica 2-opt de camino abierto a la secuencia de cada
ruta por separado (`route_resequencer.py`). La asignación árbol → ruta no cambia.
La duración de cada ruta solo puede **bajar** (2-opt es una mejora).

Flag: `config_algorithm_sweep --only-cell actual+reseq` y `upper-tmax-tmin9000+reseq`.

### Criterio de éxito (a priori)

- Cruces ≤ cruces del control correspondiente sin reseq (puede bajar a 0 en el límite)
- Travel ≤ travel del control (2-opt no empeora el travel de la ruta)
- k igual al control (no cambia la asignación)
- Balance puede bajar moderadamente; **no es fallo automático**, se reporta explícitamente

### Resultados

<!-- Llenar con tabla antes/después: celda, instancia, crossings_antes, crossings_después, travel_antes, travel_después, balance_antes, balance_después -->

---

## Fase 3a — Piso factible (`feasible-floor`)

### Descripción

Nuevo brazo donde `T_min_eff = min(T_min, β · (servicio_total + travel_NN) / k_est)`,
con k\_est sin buffer y trabajo total (servicio + travel nearest-neighbor).
β ∈ {0.85, 0.90, 0.95}. Upper target = T\_max.

**Diferencia respecto a `tmin-scaled` descartado:** ese brazo usaba `total_service // k_buffer`
(trabajo solo servicio, con buffer inflado → piso enano → balance roto). El nuevo brazo
usa trabajo total (incluye travel NN) y k sin buffer → piso converge al `actual` en régimen
saturado y lo baja solo en no saturado.

Celdas: `feasible-floor-b085`, `feasible-floor-b090`, `feasible-floor-b095`.

### Criterio de éxito (a priori)

| Métrica | Umbral |
| --- | --- |
| Cruces en n=1607 | ≤ control (`actual`) |
| Travel | ≤ control + 3 % |
| Balance | ≥ 0.80 en **todas** las instancias |
| k en n=1607 | ≤ 26 |
| Drops | 0 en todas las instancias |
| Áreas chicas (n≤157) | Cruces ≤ control y relleno ≤ control |

### Resultados

<!-- Llenar con tabla de celdas × instancias -->

---

## Fase 3b — Costo de arco convexo

### Descripción

Evaluador de costo de arco separado de la dimensión Time:
`arc_cost = ceil(travel + λ · max(0, travel − τ)² / τ)`, con τ = p95 de arcos
nearest-neighbor de la instancia. La dimensión Time sigue midiendo segundos reales
(travel + servicio). λ ∈ {1, 5, 20}.

El objetivo del término convexo: penalizar arcos largos (que corresponden a cruces y
zigzag entre áreas) sin alterar la factibilidad temporal.

Celdas: `arc-convex-l1`, `arc-convex-l5`, `arc-convex-l20`.

### Criterio de éxito (a priori)

| Métrica | Umbral |
| --- | --- |
| Cruces en n=1607 | **−≥30 %** vs control `actual` |
| Travel | ≤ control + 3 % |
| Balance | ≥ 0.80 en **todas** las instancias |
| k en n=1607 | ≤ 26 |
| Drops | 0 en todas las instancias |
| Áreas chicas | Sin empeorar cruces ni relleno vs control |

### Resultados

<!-- Llenar con tabla de λ × instancias -->

---

## Veredicto final

<!-- Si algún brazo cumple **todos** los criterios, declararlo aquí como propuesta verificada.
     No cambiar defaults de producción en este PR. -->

---

## Instrucciones de ejecución

```bash
# Fase 1 — auditoría del objetivo
docker compose -p arbocensus exec web \
  python manage.py objective_audit --dataset reference-n1607

docker compose -p arbocensus exec web \
  python manage.py objective_audit --dataset area-26-n157

# Fase 2 + 3 — barrido completo (nuevas celdas)
docker compose -p arbocensus exec web \
  python manage.py config_algorithm_sweep \
    --csv docs/experiments/objective-audit-postpass-sweep-20260718.csv \
    --only-cell actual+reseq

# Correr todas las celdas nuevas:
# actual+reseq, upper-tmax-tmin9000+reseq,
# feasible-floor-b085/b090/b095,
# arc-convex-l1/l5/l20
```
