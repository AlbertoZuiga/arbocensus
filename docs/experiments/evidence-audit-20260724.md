# Auditoría de fuerza de evidencia — serie de 16 ciclos

**Fecha**: 2026-07-24  
**Alcance**: Los 16 ciclos de la serie cerrados entre 2026-07-09 y 2026-07-24 (PR #194 a #245).  
**Método**: Lectura de los cinco defectos conocidos de instrumentación (D-a a D-e) contra los reportes y CSV versionados en `docs/experiments/`. Regla: un veredicto sigue en pie si no depende de la métrica o del instrumento defectuoso; la auditoría cambia veredictos solo donde se probó que el instrumento defectuoso fue causal.

---

## 1. Defectos conocidos y alcance

### D-a: Semillas falsas (3 copias del mismo número)

- **Descubierto**: #221 (`sweep-metrology-20260720.md`)
- **Causa**: `node_seed` no llegaba al solver; las "3 semillas" no permutaban el orden de nodos, así que las réplicas eran la misma corrida
- **Síntoma**: Todas las corridas con "semillas" `{X, X, X}` reportaban σ ≈ 0,03 %, artefacto de replicación idéntica
- **Alcance**: Ciclos #194, #196, #203, #209, #215, #217
- **Resolución**: #221 cableó `node_seed` → semillas reales; σ ahora ~2,4 %
- **Cambio de veredicto**: 14 de 28 celdas re-juzgadas

### D-b: Métrica de relleno con cero inalcanzable

- **Descubierto**: #221 (`sweep-metrology-20260720.md`)
- **Causa**: `relleno = travel − n·nn̄` usaba como cota inferior `n·nn̄`, la suma de las distancias al vecino más cercano, que ningún recorrido puede alcanzar porque viola la restricción de grado de los caminos
- **Corrección**: `relleno_msf = travel − MSF_k` (bosque generador mínimo de `k` componentes), cota válida y alcanzable
- **Alcance**: Ciclos #194–#217
- **Resolución**: #221 reemplazó la métrica; 14 de 28 veredictos cambiaron
- **Ciclos posteriores**: No lo arrastran; D-b queda resuelto

### D-c: Cruces de cuerdas — proxy parcial e invertido en n=1607

- **Descubierto**: 2026-07-23, cuantificado en #240/#241 (`crossing-metric-validation-20260723.md`)
- **Causa**: `self_crossings` cuenta cruces de líneas rectas entre paradas consecutivas; el solver optimiza tiempo de red OSRM; la app dibuja la polilínea real de calles
- **Métrica nueva**: `crossings_road` = `self_crossings` sobre la polilínea de `osrm.fetch_route_path`
- **Validación** (#240/#241):
  - ρ Spearman cuerda↔calle = **0,527** sobre las 216 filas (banda "proxy parcial" 0,50–0,80)
  - En `reference-n1607` = **−0,575** (invertido)
  - Replicado en #242: **−0,618**
  - Signo del post-pass 2-opt sobre `crossings_road`: baja o empata en 104 de 108 filas emparejadas y sube en 4; sobre cuerdas los mismos brazos decían ×2,9 a ×5,3
- **Alcance sin corrección**: Ciclos #194–#237 (todo lo anterior a #240)
- **Ciclos con corrección**: #240/#241 (miden ambas), #242/#243/#244 (usan `crossings_road` como primaria)
- **Impacto máximo**: el rechazo del post-pass en #196 por "empeorar los cruces", cuantificado después como ×8 sobre cuerdas, era artefacto de dibujo
- **Candidatos para re-juicio**: Ciclos cuyo rechazo fue **única o primariamente por cruces**

### D-d: Compuerta de balance viejo ≥0,80

- **Contexto**: #185 juzgó con balance ≥ 0,80; el estándar de esta serie es ≥ 0,60
- **Redescubrimiento**: 2026-07-24
- **Alcance**: No afecta a los ciclos de esta serie, que usan ≥ 0,60; **sí afecta a los descartes heredados de #185** (`exempt-last`)
- **Cambio medido en #185 ahora**: `tmin-scaled+exempt-last` falla 4/12 con balance ≥ 0,80; **falla 0/12 con ≥ 0,60**
- **Efecto**: Re-abre `exempt-last` para medición nueva

### D-e: Degeneración por conteo de paradas (<5 paradas)

- **Contexto**: El criterio `<5 paradas` **o** `<1 800 s` marca una ruta como degenerada
- **Problema**: La ruta de 3 paradas y 10 485 s de #228 está al 97 % de `T_max` (10 800 s) — para el censista es jornada completa, no turno mutilado
- **Redescubrimiento**: 2026-07-24
- **Cambio de criterio**: Se **elimina** la cláusula `<5 paradas`; queda solo la de duración
- **Alcance**: Ciclos que reportan `degenerate_routes`
- **Efecto medido** (sobre los CSV versionados en `docs/experiments/`): 111 filas tienen `degenerate_routes > 0`; 106 de ellas traen la columna `dur_min_sec`, y de esas **45 quedan absueltas** (`dur_min_sec ≥ 1 800`) y **61 persisten** por duración. Las 5 restantes son de barridos anteriores a la columna y no se pueden re-juzgar sin re-correr
- **Ciclos reabiertos**: `no-floor` **NO** (`dur_min` 120 s en `reference-n1607` y 1 168 s en `battery-n200`, falla la cláusula que queda); `feasible-floor-b095` **SÍ** (17 filas, `dur_min` 6 759–8 475 s, todas absueltas)

---

## 2. Matriz de auditoría: 16 ciclos × 5 defectos

Marca `✓` = el ciclo corrió bajo el defecto; `✔` = el ciclo corrige o usa la métrica ya corregida.

| Ciclo | PR | Reporte | D-a | D-b | D-c | D-d | D-e | Veredicto | Cambio en auditoría |
|---|---|---|---|---|---|---|---|---|---|
| 1a | #194 | `objective-audit-postpass-sweep-20260718.md` | ✓ | ✓ | ✓ | — | ✓ | Rechazado: travel +5,8 % contra el criterio ≤ +3 % | **NO**: el travel medido no depende de la métrica de cuerdas ni del cero de relleno |
| 1b | #196 | `objective-audit-postpass-sweep-20260718.md` | ✓ | ✓ | ✓ | — | ✓ | Rechazado: el post-pass 2-opt "empeora los autocruces" | **SÍ**: #240/#241 prueban que el empeoramiento era artefacto de cuerdas; sobre `crossings_road` el mismo post-pass baja o empata en 104 de 108 filas. Rechazo causal en D-c |
| 1c | #203 | `objective-audit-postpass-sweep-20260718.md` | ✓ | ✓ | ✓ | — | ✓ | Rechazado: los autocruces no los producen los arcos largos | **NO**: el descarte es de causalidad (arcos ≠ cruces), no de nivel de cruces; D-c no toca la premisa |
| 2 | #209 | `no-floor-balance-sweep-20260719.md` | ✓ | ✓ | ✓ | — | ✓ | Rechazado: sin piso, más cruces y rutas degeneradas | **Parcial**: la lectura de cruces era de cuerdas, pero #240/#241 la rehace sobre calle y `no-floor` sigue peor (road 73 contra 43 de `actual`). D-e no lo absuelve: `dur_min` 120 s |
| 4 | #215 | `stops-floor-sweep-20260720.md` | ✓ | ✓ | ✓ | — | ✓ | Rechazado: el piso de paradas no arregla el relleno de `area-26` | **NO**: el descarte es por relleno, no por cruces ni por conteo de paradas |
| 5 | #217 | `combined-floor-sweep-20260720.md` | ✓ | ✓ | ✓ | — | ✓ | Rechazado: el piso combinado queda inactivo en `area-26` | **NO**: el piso factible es ≤ k por aritmética; no depende de instrumento |
| 6 | #221 | `sweep-metrology-20260720.md` | ✔ corrige | ✔ corrige | — | — | — | **Corrección de instrumento** (D-a + D-b) | **Punto de corte**: semillas reales y métrica MSF; 14 de 28 celdas re-juzgadas |
| 8 | #227 | `multistart-sweep-20260721.md` | — | — | ✓ | — | ✓ | Rechazado: el multi-arranque empata, no reduce varianza | **NO**: el descarte es del propio empate en travel; D-c no interviene |
| 10 | #228 | `stops-penalty-sweep-20260722.md` | — | — | ✓ | — | ✓ | Rechazado: el piso de paradas sobre `b095` es inerte a todo umbral y fuerza | **SÍ (nomenclatura)**: la ruta que motivaba el ciclo (3 paradas, 10 485 s) **queda absuelta por D-e** — 10 485 s es el 97 % de `T_max`, no un turno mutilado. El descarte del piso de paradas se mantiene porque no compró relleno |
| 9 | #231 | `tsp-achievable-anchor-20260722.md` | — | — | — | — | — | Cierre: brecha MSF↔UB de 13–29 %; no cambia veredictos | **NO**: es posterior a #221 y no mide cruces |
| 7 | #237 | `cluster-constrained-search-20260722.md` | — | — | ✓ | — | ✓ | Rechazado (ambos brazos): los clusters blandos abandonan árboles; el warm start empeora la geometría | **NO**: el abandono de árboles y el aislamiento de los tres árboles son del territorio, no del instrumento |
| 16 | #240/#241 | `crossing-metric-validation-20260723.md` | — | — | ✔ mide | — | — | **Corrección de métrica**: construye `crossings_road` y la valida contra la calle; ρ = 0,527, y −0,575 en `reference-n1607` | **Punto de corte**: D-c queda dimensionada. Replicado en #242 (ρ = −0,618) |
| 12×13 | #242 | `floor-price-upper-target-20260723.md` | — | — | ✔ usa | — | — | `upper-tmax` rechazada: cuerdas −93 % pero `crossings_road` +42 %; falla además el relleno de `area-26` (−25 %) y `area-29` | **Validación de D-c**: leyendo solo cuerdas la celda era ganadora rotunda; la calle real la refuta |
| 19 | #243 | `regime-guard-20260724.md` | — | — | — | — | — | Rechazado: el predicado acierta 3/12 contra 8/12 del trivial | **NO**: resultado negativo pre-registrado y bien medido |
| 17 | #244 | `arc-weight-crossings-20260724.md` | — | — | ✔ usa | — | — | Rechazado: el peso lineal del arco baja cruces solo donde el travel tiene holgura | **NO**: medido con `crossings_road` ya calibrada |
| 23 | #245 | `postpass-default-20260724.md` | — | — | ✔ usa | — | — | **Adoptado**: travel baja en 12/12, `crossings_road` baja en 12/12, `k` y balance invariantes | **Capitaliza la corrección**: primer cambio de configuración de la serie, habilitado por #240/#241 |

---

## 3. Ciclos cuyo veredicto cambia bajo la auditoría

### 3.1 #196 — post-pass 2-opt intra-ruta: rechazo impugnado

**Veredicto original**: el post-pass empeora los autocruces sobre una base limpia, medido con `crossings` de cuerdas.

**Hallazgo de #240/#241**: el 2-opt minimiza tiempo de red OSRM (`matrix[a][b]`), no longitud de cuerdas. `self_crossings` une paradas consecutivas con segmentos rectos, de modo que el re-secuenciamiento fabrica cruces entre cuerdas nuevas mientras la traza real de calles mejora.

**Prueba decisiva**: signo del post-pass sobre `crossings_road`:

- Baja o empata en 104 de las 108 filas emparejadas y sube en 4
- Por brazo, la caída va de −24 % (`actual` → `+reseq`) a −45 % (`no-floor` → `+reseq`)
- Los mismos brazos, leídos en cuerdas, reportaban ×2,9 a ×5,3

**Re-juicio**: si `crossings_road` es la métrica autorizada, el post-pass limpia la geometría real. El empeoramiento de #196 es artefacto de la métrica de cuerdas.

**Cambio documentado**: el rechazo de #196 por autocruces queda impugnado. Lo que sostiene el descarte de la variante `no-floor+reseq` de ese ciclo es la degeneración y el balance, no los cruces. La re-medición completa se hizo en #245, que sí adopta el post-pass.

---

### 3.2 #209 — sin piso: lectura de cruces corregida, veredicto intacto

**Veredicto original**: rechazado; más cruces que `actual`, rutas degeneradas y balance bajo.

**Auditoría**:

- D-c: la comparación de cruces se hizo en cuerdas, y en `reference-n1607` la correlación cuerda↔calle está invertida (−0,575). Pero #240/#241 vuelve a medir `no-floor` sobre calle real y sigue siendo peor: 73 contra 43 de `actual`.
- D-e: `no-floor` no entra en las filas absueltas — su `dur_min` es 120 s en `reference-n1607` y 1 168 s en `battery-n200`, ambos bajo el umbral de 1 800 s que queda vigente.

**Cambio documentado**: la lectura de cruces cambia de instrumento pero no de signo, y la degeneración es de duración, no de conteo. El veredicto se mantiene con evidencia mejor, no peor.

---

### 3.3 #228 — piso de paradas sobre `b095`: la ruta deja de ser degenerada

**Veredicto original**: el piso de paradas es inerte sobre `b095` a todo umbral y fuerza; la ruta corta de `b095` figura como degenerada.

**Auditoría**:

- D-e: la ruta que motivaba el ciclo tiene 3 paradas y 10 485 s de duración contra un `T_max` de 10 800 s, es decir el 97 % de la capacidad dura. Con la cláusula de conteo eliminada **deja de contar como degenerada**. Las 17 filas de `feasible-floor-b095` con `degenerate_routes > 0` tienen `dur_min` entre 6 759 s y 8 475 s: todas quedan absueltas.
- D-d: no aplica; `b095` pasa el balance ≥ 0,60 en las 12 instancias, con mínimo 0,652 medido en #215.

**Cambio documentado**: la ruta corta de `b095` es estructura territorial —tres árboles aislados a ~2,8 h de camino— y no un defecto de la solución. Lo que se descarta en #228 es el piso de paradas como palanca, porque no compra relleno; el descarte no descansa en la etiqueta de degeneración. `feasible-floor-b095` queda pendiente de re-juicio con el criterio nuevo, y su obstáculo conocido es el relleno de `area-26` (−20,8 % contra el −50 % exigido en #215).

---

### 3.4 #242 — `upper-tmax`: refutada, y solo gracias a la métrica corregida

**Lectura en cuerdas de la celda `upper@T_max` con piso**: −93 % de `crossings` en `reference-n1607`, que la haría ganadora rotunda.

**Re-juicio con `crossings_road`**:

- `crossings_road` en `reference-n1607`: **+42 %** (41,0 → 58,3), no −93 %
- Balance cae de 0,849 a 0,723, que aún pasa el umbral de 0,60
- La ruta degenerada que aparece en 2 de 3 semillas lo es por conteo de paradas, de modo que D-e la absuelve
- Áreas: falla el criterio de relleno, con `area-26` en −25 % contra el −30 % exigido y `area-29` sin moverse

**Veredicto corregido**: refutada. Con D-e aplicado y el balance dentro de umbral, lo que sostiene el rechazo es exactamente `crossings_road` más el relleno de las áreas.

**Cambio documentado**: este es el caso donde la corrección de instrumento fue indispensable. Sin `crossings_road`, la única lectura disponible declaraba ganadora una celda que empeora la geometría que el censista camina.

---

### 3.5 #245 — post-pass 2-opt adoptado como configuración por defecto

**Situación de partida**: el post-pass estaba descartado desde #196 por empeorar los autocruces medidos en cuerdas.

**Re-evaluación**:

- Línea base de `reference-n1607` re-corrida con semillas reales
- Travel 59 898 → 58 351 s (−2,6 %) en `reference-n1607`, media −16,2 % sobre las 12 instancias
- `k` y balance invariantes, cero rutas degeneradas
- Las 12 instancias bajan travel y bajan `crossings_road`: mejora de Pareto, sin intercambio

**Veredicto**: adoptado como configuración por defecto, el primer cambio de configuración de la serie. No sale de barrer términos del objetivo, sino de re-medir con el instrumento corregido.

**Encadenamiento**:

1. #221 corrige semillas y cero de relleno → 14 de 28 celdas re-juzgadas
2. #240/#241 dimensiona la métrica de cruces → el empeoramiento de #196 era artefacto de dibujo
3. #245 capitaliza la corrección → primer cambio de configuración por defecto de la serie

---

## 4. Ciclos cuyo veredicto NO cambia

### La métrica de cruces no es causal en #194, #203, #215, #217, #227, #237

- #194: rechazo por travel (+5,8 % contra el criterio ≤ +3 %)
- #203: rechazo de causalidad — los cruces no los producen los arcos largos
- #215: rechazo por el relleno de `area-26`
- #217: rechazo por aritmética — el piso factible queda inactivo en `area-26`
- #227: rechazo por el empate en travel entre arranques al mismo presupuesto de solver
- #237: rechazo por abandono de árboles y por el aislamiento geográfico de los tres árboles

### Absoluciones por duración que no reviven candidatos

- #228 (`b095`): la ruta corta queda absuelta, pero el piso de paradas sigue descartado por inerte
- #209 (`no-floor`): no queda absuelto — `dur_min` 120 s

### Resultados negativos bien medidos

- #231: cierre de calibración posterior a #221; no mide cruces
- #243: resultado negativo, pre-registrado y con salvaguardas cumplidas
- #244: resultado negativo medido ya con `crossings_road`

---

## 5. Síntesis: Qué cambió en esta auditoría

| Categoría | Ciclos | Efecto |
|---|---|---|
| Veredicto impugnado por D-c | #196 | El post-pass no empeoraba la geometría real; el rechazo por cruces cae |
| Veredicto sostenido con instrumento nuevo | #209, #242 | La lectura cambia de cuerdas a calle; en #209 el signo se mantiene, en #242 se invierte y la celda pasa de ganadora a refutada |
| Veredictos que no dependen del instrumento | #194, #203, #215, #217, #227, #231, #237, #243, #244 | Descartes por travel, relleno, aritmética o causalidad |
| Etiqueta de degeneración corregida | #228 | La ruta de 3 paradas y 10 485 s deja de contar como degenerada; el descarte del piso de paradas se mantiene por otra razón |
| Correcciones de instrumento | #221, #240/#241 | #221 re-juzgó 14 de 28 celdas; #240/#241 dimensionó la métrica de cruces |
| Primer cambio de configuración por defecto | #245 | Habilitado por la corrección de métrica, no por un barrido |

---

## 6. Limitaciones que quedan documentadas

1. **Semillas (D-a)**: las corridas de #194 a #217 tenían una réplica efectiva disfrazada de tres. La dispersión reportada de σ ≈ 0,03 % es artefacto de replicación idéntica y no describe la convergencia del solver. Ningún ciclo de ese tramo se apoya en barras de error utilizables. El defecto se descubrió y se corrigió dentro de la propia serie (#221), a costa de re-juzgar 14 de 28 celdas.

2. **Cuerdas contra calles (D-c)**: la métrica de autocruces sobre cuerdas rectas es un proxy parcial de la geometría real (ρ Spearman 0,527) e invertido en la instancia de referencia (−0,575 en `reference-n1607`, −0,618 en la réplica de #242). Lo anterior a #240/#241 que se rechazó únicamente por cruces queda bajo revisión, y la única celda que las cuerdas hacían ganadora, `upper-tmax`, resulta refutada al medir sobre calle. Las comparaciones relativas dentro de un mismo ciclo siguen siendo homogéneas —todos los brazos se midieron con la misma vara—; lo que no se sostiene es la lectura absoluta.

3. **Paradas contra duración (D-e)**: el criterio de ruta degenerada mezclaba un proxy de aislamiento geográfico, el conteo de paradas, con el perjuicio operativo real, la duración. Eliminada la cláusula de conteo, de las 106 filas re-juzgables 45 quedan absueltas y 61 persisten. La ruta que motivó el criterio —3 paradas, 10 485 s, 97 % de `T_max`— deja de figurar como degenerada, aunque el candidato que la contenía sigue descartado por relleno.

4. **Lectura de conjunto**: en los 16 ciclos, los cambios de mayor efecto vinieron de corregir instrumentos —semillas y cota de relleno en #221, métrica de cruces en #240/#241— y no de barrer términos del objetivo. El único cambio de configuración por defecto de toda la serie (#245) es consecuencia directa de una de esas correcciones.

---

## 7. Cambio de criterio registrado

**2026-07-24**: se elimina la cláusula `<5 paradas` del criterio de rutas degeneradas. Razón: el conteo de paradas es un proxy de aislamiento geográfico, no de perjuicio operativo, y la ruta corta la reproduce cualquier método que respete la geografía. Queda vigente solo la cláusula de duración (`< 1 800 s`). Efecto sobre los CSV versionados: de las 106 filas con `degenerate_routes > 0` que traen `dur_min_sec`, 45 quedan absueltas y 61 persisten.

Los ciclos #194 a #228 reportan la cifra anterior; cualquier re-juicio sobre ellos debe declarar explícitamente qué criterio aplica.

---

## Apéndice: reportes y CSV versionados

- `20260713-real-case-metrics-spatial.csv` — línea base de `reference-n1607` anterior al post-pass
- `20260724-213512-postpass-baseline.csv` — línea base de `reference-n1607` con post-pass y semillas reales
- `objective-audit-postpass-sweep-20260718.md` — #194, #196 y #203
- `no-floor-balance-sweep-20260719.md` — #209
- `stops-floor-sweep-20260720.md` — #215
- `combined-floor-sweep-20260720.md` — #217
- `sweep-metrology-20260720.md` — #221
- `multistart-sweep-20260721.md` — #227
- `stops-penalty-sweep-20260722.md` — #228
- `tsp-achievable-anchor-20260722.md` — #231
- `cluster-constrained-search-20260722.md` — #237
- `crossing-metric-validation-20260723.md` — #240 y #241
- `floor-price-upper-target-20260723.md` — #242
- `regime-guard-20260724.md` — #243
- `arc-weight-crossings-20260724.md` — #244
- `postpass-default-20260724.md` — #245

---

**Conclusión**: de los 16 ciclos, uno queda con el veredicto impugnado por la métrica corregida (#196), dos se releen con el instrumento nuevo sin que cambie el descarte final (#209, #242), dos son correcciones de instrumento (#221, #240/#241), uno es el único cambio de configuración por defecto de la serie (#245) y los diez restantes son resultados negativos cuyo descarte no depende de ninguno de los cinco defectos. La auditoría no invalida las comparaciones relativas —todos los brazos de un mismo ciclo se midieron con la misma vara—, pero acota la lectura absoluta de la métrica de cuerdas y deja registrado qué evidencia es fuerte y cuál no.
