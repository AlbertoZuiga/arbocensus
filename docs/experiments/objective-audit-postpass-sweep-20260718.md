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

Celdas corridas sobre las 12 instancias, 3 semillas por celda (media sobre semillas).
Dispersión entre semillas casi nula salvo `feasible-floor-b095` en n=1607 (cruces 39/5/6
por semilla, spread 34 — el piso más alto deja al solver en un régimen inestable) y
`feasible-floor-b085` en battery-n1000 (spread 2).

#### k / cruces / balance por celda

| Instancia | control (k / cruces / bal) | β=0.85 | β=0.90 | β=0.95 |
| --- | ---: | ---: | ---: | ---: |
| battery-n50 | 2 / 5 / 0.998 | 1 / 0 / 1.000 | 1 / 0 / 1.000 | 1 / 0 / 1.000 |
| battery-n100 | 2 / 3 / 0.946 | 2 / 0 / 0.660 | 2 / 0 / 0.652 | 2 / 0 / 0.652 |
| battery-n200 | 4 / 2 / 0.832 | 4 / 4 / 0.597 | 4 / 5 / 0.712 | 4 / 4 / 0.679 |
| battery-n400 | 7 / 2 / 0.987 | 6 / 2 / 0.820 | 6 / 6 / 0.826 | 6 / 6 / 0.866 |
| battery-n800 | 12 / 29 / 0.851 | 12 / 5 / 0.749 | 12 / 6 / 0.595 | 12 / 6 / 0.749 |
| battery-n1000 | 15 / 56 / 0.847 | 14.3 / 9.3 / 0.829 | 15 / 3 / 0.657 | 15 / 9 / 0.688 |
| battery-sparse-n250 | 5 / 2 / 0.946 | 5 / 2 / 0.639 | 5 / 2 / 0.617 | 5 / 1 / 0.768 |
| battery-sparse-n500 | 9 / 12.3 / 0.834 | 8 / 4 / 0.854 | 8 / 4 / 0.875 | 8 / 4 / 0.875 |
| area-26-n157 | 3 / 0 / 0.877 | 3 / 0 / 0.754 | 3 / 0 / 0.821 | 3 / 0 / 0.838 |
| area-27-n72 | 2 / 6 / 1.000 | 1 / 0 / 1.000 | 1 / 0 / 1.000 | 1 / 0 / 1.000 |
| area-29-n43 | 1 / 0 / 1.000 | 1 / 0 / 1.000 | 1 / 0 / 1.000 | 1 / 0 / 1.000 |
| reference-n1607 | 25 / 88.7 / 0.833 | 25 / 10 / 0.789 | 25 / 11.7 / 0.791 | 25 / 16.7 / 0.667 |

#### Δ travel vs control / relleno (s)

| Instancia | travel ctl (s) | relleno ctl (s) | β=0.85 | β=0.90 | β=0.95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 8 399 | 6 375 | −59.3 % / 1 352 | −59.3 % / 1 352 | −59.3 % / 1 352 |
| battery-n100 | 4 244 | 1 784 | −1.7 % / 1 713 | +0.3 % / 1 796 | +0.3 % / 1 796 |
| battery-n200 | 8 254 | 4 776 | +0.7 % / 4 833 | −3.8 % / 4 463 | +0.2 % / 4 796 |
| battery-n400 | 14 557 | 9 039 | −10.8 % / 7 452 | −10.4 % / 7 508 | −1.4 % / 8 826 |
| battery-n800 | 19 702 | 10 739 | +8.5 % / 12 419 | +15.4 % / 13 773 | +10.0 % / 12 702 |
| battery-n1000 | 26 598 | 15 646 | +4.2 % / 16 754 | +10.1 % / 18 324 | +2.1 % / 16 217 |
| battery-sparse-n250 | 15 734 | 7 324 | −5.4 % / 6 479 | −2.6 % / 6 920 | −1.3 % / 7 115 |
| battery-sparse-n500 | 23 016 | 13 574 | −6.9 % / 11 959 | −5.9 % / 12 202 | −5.9 % / 12 202 |
| area-26-n157 | 4 962 | 2 579 | −12.2 % / 1 972 | −8.9 % / 2 137 | −10.8 % / 2 042 |
| area-27-n72 | 5 738 | 5 207 | −73.8 % / 965 | −73.8 % / 963 | −73.8 % / 963 |
| area-29-n43 | 2 022 | 1 634 | −50.6 % / 611 | −50.6 % / 611 | −50.6 % / 611 |
| reference-n1607 | 60 566 | 33 510 | −0.3 % / 33 312 | −0.7 % / 33 092 | +0.2 % / 33 621 |

Drops = 0 en las 108 filas del brazo. k cae donde el piso reducido permite consolidar
(battery-n50 2→1, battery-n400 7→6, battery-sparse-n500 9→8, area-27 2→1); en n=1607
k = 25 idéntico al control.

#### Estado de cada criterio (a priori)

| Criterio | β=0.85 | β=0.90 | β=0.95 | Detalle |
| --- | --- | --- | --- | --- |
| Cruces n=1607 ≤ control | ✅ | ✅ | ✅ | 88.7 → 10 / 11.7 / 16.7 (−81 a −89 %) |
| Travel ≤ control +3 % | ❌ | ❌ | ❌ | Peor caso battery-n800: +8.5 / +15.4 / +10.0 %; en n=1607 sí cumple (−0.3 / −0.7 / +0.2 %) |
| Balance ≥ 0.80 en todas | ❌ | ❌ | ❌ | Mínimos 0.597 (n200) / 0.595 (n800) / 0.652 (n100); n=1607 también falla: 0.789 / 0.791 / 0.667 |
| k n=1607 ≤ 26 | ✅ | ✅ | ✅ | 25 en los tres β |
| Drops 0 en todas | ✅ | ✅ | ✅ | 0 en las 108 filas |
| Áreas chicas: cruces ≤ ctl y relleno ≤ ctl | ✅ | ✅ | ✅ | Cruces 0 en las tres áreas; relleno −24 % (area-26), −81 % (area-27), −63 % (area-29) |

**Ningún β cumple el criterio completo.** Fallan travel (+3 %) y balance (≥0.80), ambos
concentrados en la batería sintética densa media (n=100–1000).

#### Lectura

- El piso factible hace exactamente lo prometido en régimen de relleno: en las áreas
  reales chicas elimina el relleno de raíz (area-27: travel −73.8 %, relleno 5 207 → 965 s,
  y además consolida 2 rutas en 1 sin relleno) manteniendo cruces en 0. A diferencia del
  2-opt de Fase 2, esto NO rompe el contrato del piso: T\_min\_eff baja por construcción,
  así que las rutas cortas son legales, no violaciones.
- La promesa "converge a `actual` en saturado" se cumple a medias en n=1607: k, travel y
  relleno son indistinguibles del control, pero los cruces caen 88.7 → 10 (−89 %) y el
  balance cae 0.833 → 0.789. El piso efectivo queda algo bajo T\_min incluso con
  saturación medida ≈ 0.94 (`saturation_mean`; `sat_estimated`, la que fija el piso, es
  0.714), y esa holgura la usa el solver para alargar unas rutas y acortar
  otras: geometría mucho más limpia, balance bajo el umbral.
- El mecanismo de fallo en la batería media es el mismo: piso bajo → el solver deja rutas
  desiguales (balance 0.60–0.75) y en n=800/n=1000 además gasta más travel (+8 a +15 %)
  reorganizando la partición. El β mayor no lo corrige (β=0.95 tiene el peor balance en
  n=1607: 0.667, con dispersión alta entre semillas).

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

Celdas corridas sobre las 12 instancias, 3 semillas por celda (media sobre semillas).
τ (p95 de arcos nearest-neighbor) por instancia: 27.6 s (area-29) a 112.6 s (battery-n50);
44.1 s en n=1607. Dispersión entre semillas notable en varias celdas (λ=1 battery-n800
spread de cruces 20, λ=5 battery-n400 spread 73 con k 6/6/7): el término convexo hace el
paisaje de búsqueda más ruidoso que el control.

#### k / cruces / balance por celda

| Instancia | control (k / cruces / bal) | λ=1 | λ=5 | λ=20 |
| --- | ---: | ---: | ---: | ---: |
| battery-n50 | 2 / 5 / 0.998 | 2 / 25 / 1.000 | 2 / 36.7 / 0.999 | 2 / 41 / 1.000 |
| battery-n100 | 2 / 3 / 0.946 | 2 / 0 / 0.838 | 2 / 0 / 0.989 | 2 / 2 / 0.998 |
| battery-n200 | 4 / 2 / 0.832 | 4 / 1 / 0.886 | 4 / 12.3 / 0.887 | 4 / 16 / 0.877 |
| battery-n400 | 7 / 2 / 0.987 | 6 / 20 / 0.825 | 6.3 / 49.3 / 0.815 | 6 / 44 / 0.944 |
| battery-n800 | 12 / 29 / 0.851 | 12 / 47.7 / 0.841 | 12 / 24 / 0.842 | 12 / 49.3 / 0.831 |
| battery-n1000 | 15 / 56 / 0.847 | 15 / 53.3 / 0.832 | 14 / 55.3 / 0.866 | 14 / 57 / 0.893 |
| battery-sparse-n250 | 5 / 2 / 0.946 | 5.7 / 2.7 / 0.926 | 6 / 5 / 0.810 | 6 / 7 / 0.878 |
| battery-sparse-n500 | 9 / 12.3 / 0.834 | 8 / 15.7 / 0.879 | 9 / 34 / 0.862 | 8 / 22 / 0.842 |
| area-26-n157 | 3 / 0 / 0.877 | 3 / 0 / 0.815 | 3 / 1 / 0.862 | 3 / 12 / 0.834 |
| area-27-n72 | 2 / 6 / 1.000 | 2 / 45 / 1.000 | 2 / 113 / 1.000 | 1 / 2 / 1.000 |
| area-29-n43 | 1 / 0 / 1.000 | 1 / 11 / 1.000 | 1 / 26 / 1.000 | 1 / 40 / 1.000 |
| reference-n1607 | 25 / 88.7 / 0.833 | 25 / 113 / 0.845 | 25 / 72.3 / 0.839 | 25 / 90 / 0.844 |

#### Δ travel vs control / relleno (s)

| Instancia | travel ctl (s) | relleno ctl (s) | λ=1 | λ=5 | λ=20 |
| --- | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 8 399 | 6 375 | −0.2 % / 6 356 | −0.2 % / 6 357 | −0.2 % / 6 358 |
| battery-n100 | 4 244 | 1 784 | −5.1 % / 1 568 | −4.7 % / 1 586 | −8.4 % / 1 426 |
| battery-n200 | 8 254 | 4 776 | −9.5 % / 3 992 | −7.9 % / 4 127 | −9.6 % / 3 984 |
| battery-n400 | 14 557 | 9 039 | −22.4 % / 5 767 | −9.5 % / 7 647 | −16.5 % / 6 622 |
| battery-n800 | 19 702 | 10 739 | +16.7 % / 14 039 | +0.9 % / 10 910 | +2.1 % / 11 143 |
| battery-n1000 | 26 598 | 15 646 | +9.4 % / 18 135 | −6.8 % / 13 835 | −6.9 % / 13 802 |
| battery-sparse-n250 | 15 734 | 7 324 | +2.0 % / 7 658 | +9.0 % / 8 780 | −2.3 % / 7 001 |
| battery-sparse-n500 | 23 016 | 13 574 | −12.1 % / 10 769 | +9.5 % / 15 760 | −16.5 % / 9 766 |
| area-26-n157 | 4 962 | 2 579 | −7.6 % / 2 200 | −0.9 % / 2 535 | −4.5 % / 2 357 |
| area-27-n72 | 5 738 | 5 207 | −0.1 % / 5 200 | −0.1 % / 5 203 | −75.2 % / 886 |
| area-29-n43 | 2 022 | 1 634 | +0.0 % / 1 635 | +0.1 % / 1 636 | +0.2 % / 1 638 |
| reference-n1607 | 60 566 | 33 510 | +6.0 % / 37 139 | −1.2 % / 32 787 | −1.8 % / 32 401 |

Drops = 0 en las 108 filas del brazo.

#### Estado de cada criterio (a priori)

| Criterio | λ=1 | λ=5 | λ=20 | Detalle |
| --- | --- | --- | --- | --- |
| Cruces n=1607 −≥30 % | ❌ | ❌ | ❌ | 88.7 → 113 (+27 %) / 72.3 (−18 %) / 90 (+1.5 %) — nadie llega a −30 % |
| Travel ≤ control +3 % | ❌ | ❌ | ✅ | λ=1: +16.7 % (n800), +6.0 % (n=1607); λ=5: +9.5 % (sparse-n500); λ=20: peor caso +2.1 % |
| Balance ≥ 0.80 en todas | ✅ | ✅ | ✅ | Mínimos 0.815 / 0.810 / 0.831 |
| k n=1607 ≤ 26 | ✅ | ✅ | ✅ | 25 en los tres λ |
| Drops 0 en todas | ✅ | ✅ | ✅ | 0 en las 108 filas |
| Áreas chicas: sin empeorar cruces ni relleno | ❌ | ❌ | ❌ | Cruces explotan: area-29 0 → 11/26/40, area-27 6 → 45/113 (λ=20 baja a 2 pero solo porque consolida k 2→1); relleno sin cambio material (Δ ≤ +0.2 % salvo λ=20 area-27 −75 % por la consolidación) |

**Ningún λ cumple el criterio completo; el criterio central (cruces −30 % en n=1607) no lo
cumple ninguno.** La hipótesis "penalizar arcos largos ataca los cruces" queda refutada.

#### Lectura

- El término convexo minimiza arcos **largos de red**, pero los cruces se miden sobre las
  cuerdas geométricas. Al castigar arcos sobre τ, el solver prefiere encadenar muchos
  saltos cortos aunque zigzagueen: en las instancias compactas (áreas chicas, battery-n50)
  τ es tan bajo que el término domina y la geometría colapsa (area-29 0 → 40 cruces con
  λ=20, con travel idéntico). Es el mismo divorcio red/geometría que hundió al 2-opt en
  Fase 2, ahora dentro del objetivo.
- En n=1607 el efecto neto es ruido direccional: λ=1 empeora (+27 % cruces, +6 % travel),
  λ=5 mejora algo (−18 %), λ=20 vuelve al punto de partida (+1.5 %). No hay dosis-respuesta:
  el término no captura el mecanismo que produce los cruces en el denso real (asignación
  entrelazada entre rutas, no arcos individualmente largos).
- Los interleave confirman: en n=1607 sube de 95.2 (control) a 119.2 / 134.4 / 108.0 —
  el brazo **aumenta** el entrelazado que pretendía atacar.

---

## Veredicto final

**Ninguna de las cuatro propuestas evaluadas en este ciclo queda verificada contra su
criterio a priori completo.** No se cambia ningún default de producción.

| Fase | Propuesta | Veredicto | Resumen |
| --- | --- | --- | --- |
| 1 | Neutralizar cargo de vehículos vacíos | **Descartada (el cargo no existe)** | OR-Tools omite del objetivo los vehículos sin uso; el buffer +5 es inocuo. En n=1607 el objetivo real lo domina soft\_upper (83 %). |
| 2 | Post-pass 2-opt intra-ruta | **Condicional, no general** | Gratis sobre `actual` en denso saturado (n=1607: cruces −28 %, travel −2.9 %); reintroduce cruces sobre bases limpias y vacía rutas bajo T\_min en régimen de relleno. |
| 3a | Piso factible (β·trabajo/k) | **No verificada — falla balance y travel** | Elimina el relleno de raíz en áreas chicas (relleno −24 a −81 %, cruces 0, sin violar contrato) y desploma cruces en n=1607 (88.7 → 10, −89 %), pero el balance cae bajo 0.80 en la batería media Y en n=1607 (0.789), con travel +8 a +15 % en n=800/1000. |
| 3b | Costo de arco convexo | **Refutada** | Ningún λ alcanza −30 % de cruces en n=1607 (mejor: −18 % con λ=5); en áreas compactas multiplica los cruces (0 → 40) y aumenta el interleave. El mecanismo de los cruces no son arcos largos. |

Síntesis transversal de las tres fases:

- Los dos regímenes documentados exigen medicinas opuestas. En **saturado** (n=1607) el
  problema son los cruces por asignación entrelazada, y lo mejor observado sigue siendo
  la familia "subir el techo" (`upper-tmax-tmin9000`, barrido previo) o, sin tocar el
  objetivo, el 2-opt sobre `actual`. En **relleno** (áreas chicas) el problema es el piso
  inalcanzable, y el piso factible lo resuelve limpiamente — es el primer brazo que mata
  el relleno sin violar el contrato de T\_min, porque redefine el contrato por factibilidad.
- El costo del piso factible es balance: al soltar el piso, el solver ya no tiene incentivo
  para igualar duraciones. Cualquier iteración futura de esta idea necesita un término de
  balance explícito que no dependa del piso (p. ej. span cost sobre Time, ya medido como
  nulo en el barrido previo, o un piso relativo al máximo de la solución), no otro ajuste
  de β: β∈{0.85, 0.90, 0.95} no mostró dosis-respuesta en balance.
- La vía "moldear la geometría vía costo de arco" queda cerrada con dos refutaciones
  coherentes (2-opt en Fase 2, término convexo en Fase 3b): travel de red y limpieza
  geométrica no son proxies mutuos en este dominio.

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
