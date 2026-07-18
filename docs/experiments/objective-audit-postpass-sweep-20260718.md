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

Celdas corridas sobre las 12 instancias de la suite, 3 semillas por celda (144 filas en el
CSV; media sobre semillas — la dispersión entre semillas fue casi nula, spread de cruces
0–1 en todas las celdas). Nota metodológica: cada celda `+reseq` es una corrida de solver
**independiente** de su control (no la misma solución base re-secuenciada); las diferencias
de travel de ±0,2 % (p. ej. battery-n800, +0,1 %) son ruido entre corridas, no un 2-opt
empeorando su propia ruta — por construcción el 2-opt es monótono sobre el travel de red.

#### `actual` vs `actual+reseq`

| Instancia | k | Cruces antes → después | Travel antes → después (s) | Δ travel | Balance antes → después |
| --- | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 2 | 5.0 → 4.0 | 8399 → 4359 | −48.1 % | 0.998 → 0.992 |
| battery-n100 | 2 | 3.0 → 2.0 | 4244 → 3944 | −7.1 % | 0.946 → 0.969 |
| battery-n200 | 4 | 2.0 → 8.0 | 8254 → 7247 | −12.2 % | 0.832 → 0.824 |
| battery-n400 | 7 | 2.0 → 20.0 | 14557 → 13990 | −3.9 % | 0.987 → 0.968 |
| battery-n800 | 12 | 29.0 → 28.0 | 19702 → 19729 | +0.1 % | 0.851 → 0.851 |
| battery-n1000 | 15 | 56.0 → 51.0 | 26598 → 25605 | −3.7 % | 0.847 → 0.842 |
| battery-sparse-n250 | 5 | 2.0 → 3.0 | 15734 → 15682 | −0.3 % | 0.946 → 0.941 |
| battery-sparse-n500 | 9 | 12.3 → 17.0 | 23016 → 22095 | −4.0 % | 0.834 → 0.814 |
| area-26-n157 | 3 | 0.0 → 4.0 | 4962 → 4835 | −2.6 % | 0.877 → 0.874 |
| area-27-n72 | 2 | 6.0 → 3.0 | 5738 → 2538 | −55.8 % | 1.000 → 0.807 |
| area-29-n43 | 1 | 0.0 → 6.0 | 2022 → 1024 | −49.4 % | 1.000 → 1.000 |
| reference-n1607 | 25 | 88.7 → 64.0 | 60566 → 58818 | −2.9 % | 0.833 → 0.829 |

#### `upper-tmax-tmin9000` vs `upper-tmax-tmin9000+reseq`

| Instancia | k | Cruces antes → después | Travel antes → después (s) | Δ travel | Balance antes → después |
| --- | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 1 | 0.0 → 3.0 | 3419 → 3333 | −2.5 % | 1.000 → 1.000 |
| battery-n100 | 2 | 4.0 → 8.0 | 5961 → 4292 | −28.0 % | 1.000 → 0.982 |
| battery-n200 | 4 | 4.0 → 5.0 | 12024 → 10536 | −12.4 % | 0.990 → 0.943 |
| battery-n400 | 6 | 7.0 → 30.0 | 13730 → 12222 | −11.0 % | 0.836 → 0.820 |
| battery-n800 | 12 | 5.0 → 31.0 | 22400 → 20134 | −10.1 % | 0.839 → 0.840 |
| battery-n1000 | 15 | 5.0 → 49.0 | 28670 → 25714 | −10.3 % | 0.842 → 0.833 |
| battery-sparse-n250 | 5 | 2.0 → 6.0 | 17231 → 16054 | −6.8 % | 0.905 → 0.886 |
| battery-sparse-n500 | 8 | 4.0 → 19.7 | 20950 → 19631 | −6.3 % | 0.851 → 0.854 |
| area-26-n157 | 3 | 2.0 → 7.0 | 8140 → 5711 | −29.8 % | 0.995 → 0.802 |
| area-27-n72 | 2 | 27.0 → 4.0 | 9332 → 2410 | −74.2 % | 1.000 → 0.885 |
| area-29-n43 | 1 | 15.0 → 2.0 | 3821 → 1069 | −72.0 % | 1.000 → 1.000 |
| reference-n1607 | 25 | 6.0 → 51.0 | 60367 → 56764 | −6.0 % | 0.837 → 0.801 |

#### Estado de cada criterio

| Criterio | Estado | Detalle |
| --- | --- | --- |
| Cruces ≤ control | **NO cumple (global)** | Sobre `actual`: cumple en n=1607 (88.7 → 64, −28 %), n=1000, n=800, n=100, n=50 y area-27; falla en n=200 (2 → 8), n=400 (2 → 20), dispersas y áreas ya limpias (area-26 0 → 4, area-29 0 → 6). Sobre `upper-tmax-tmin9000`: falla en casi todo el rango denso — el control ya tenía cruces casi nulos y el re-secuenciado los **reintroduce** (n=1607: 6 → 51; n=1000: 5 → 49; n=800: 5 → 31); solo mejora en áreas con relleno alto (area-27 27 → 4, area-29 15 → 2). |
| Travel ≤ control | **Cumple** | Reducción en 23 de 24 pares (hasta −74 % en áreas con relleno); la única alza es +0,1 % en battery-n800 sobre `actual`, dentro del ruido entre corridas independientes de solver. |
| k igual al control | **Cumple** | k idéntico en los 24 pares; drops = 0 en todas las celdas. |
| Balance (reportar antes/después) | **Baja moderada** | Peores caídas: area-26 sobre `upper` 0.995 → 0.802, area-27 sobre `actual` 1.000 → 0.807, n=1607 sobre `upper` 0.837 → 0.801. Nunca cae bajo 0.80. En denso sobre `actual` la caída es marginal (n=1607: 0.833 → 0.829). |

#### Lectura

- El 2-opt minimiza travel de **red** (matriz OSRM); los cruces se miden sobre las cuerdas
  geométricas entre paradas consecutivas. Camino de red mínimo ≠ geometría limpia: por eso
  el re-secuenciado puede bajar travel y a la vez **subir** cruces, y lo hace de forma
  sistemática cuando la solución base ya era geométricamente limpia (todo el rango denso de
  `upper-tmax-tmin9000`, y las áreas limpias de `actual`).
- En régimen de relleno (áreas chicas bajo T\_min), el 2-opt destruye el relleno: travel
  −50 a −74 % y la duración de esas rutas cae muy por debajo de T\_min (el déficit de
  servicio no cambia porque la asignación es intacta). Esto rompe el contrato del piso
  T\_min aunque mejore travel y cruces locales.
- El único uso donde el post-pass cumple todos los criterios a la vez es sobre `actual`
  en el denso real n=1607: cruces −28 %, travel −2.9 %, balance −0.004, k y drops
  intactos, con costo de cómputo despreciable (2-opt corre en milisegundos frente a los
  120 s del solver).

#### Veredicto Fase 2

El criterio a priori "cruces ≤ control" **no se cumple globalmente**, así que el post-pass
no queda verificado como mejora general. Resultado condicional: como post-pass de
`actual` en instancias densas saturadas (n=1607) es una mejora gratuita (−28 % cruces,
−2.9 % travel); combinado con `upper-tmax-tmin9000` es contraproducente (reintroduce los
cruces que ese brazo elimina), y en régimen de relleno vacía las rutas por debajo de
T\_min. No se propone cambio de defaults de producción.

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
