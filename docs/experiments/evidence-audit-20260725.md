# M24: Auditoría de fuerza de evidencia — Serie Track M (16 ciclos)

**Fecha**: 2026-07-25  
**Alcance**: Ciclos M1–M9, M7, M16–M17, M19, M23 cerrados entre 2026-07-09 y 2026-07-24.  
**Método**: Lectura cíclica de los cinco defectos conocidos de instrumentación (D-a a D-e) contra reportes y CSV versionados. Regla: un veredicto sigue en pie si no depende de la métrica/instrumento defectuoso; la auditoría cambia veredictos solo donde se probó que el instrumento defectuoso fue causal.

---

## 1. Defectos conocidos y alcance

### D-a: Semillas falsas (3 copias del mismo número)
- **Descubierto**: F20 (#221, julio 2026)
- **Causa**: `node_seed` no se pasaba al solver OR-Tools; las "3 semillas" eran 3 permutaciones del mismo nodo inicial
- **Síntoma**: Todas las corridas con "semillas" `{X, X, X}` convergían a σ ≈0,03 %, artefacto de replicación idéntica
- **Alcance**: Ciclos #194, #196, #203, #209, #215, #217
- **Resolución**: #221 cableó `node_seed` → semillas reales; σ ahora ~2,4 %
- **Cambio de veredicto**: 14 de 28 celdas re-juzgadas (F21)

### D-b: Métrica de relleno con cero inalcanzable
- **Descubierto**: F20/F21 (#221)
- **Causa**: `relleno = travel − n·nn̄` usaba mínimo teórico `n·nn̄` que viola grado 2 de grafos → era negativo inalcanzable
- **Corrección**: `relleno_msf = travel − MSF_k` (mínimo spanning forest realista)
- **Alcance**: Ciclos #194–#217
- **Resolución**: #221 reemplazó métrica; 14 de 28 veredictos cambiaron
- **Ciclos posteriores**: No lo arrastran; D-b es historia resolvida

### D-c: Cruces de cuerdas — proxy parcial e invertido en n=1607
- **Descubierto**: F36 (2026-07-23), cuantificado en F40 (#240/#241)
- **Causa**: `self_crossings` cuenta cruces de líneas rectas entre paradas consecutivas; el solver optimiza tiempo de red OSRM; la app dibuja la polilínea real de calles
- **Métrica nueva**: `crossings_road` = `self_crossings` sobre polilínea de `osrm.fetch_route_path`
- **Validación** (M16, #240/#241):
  - ρ Spearman cuerda↔calle = **0,527** (banda "proxy parcial" 0,50–0,80)
  - En `reference-n1607` = **−0,575** (invertido)
  - Replicado en #242: **−0,618**
  - Signo del 2-opt sobre `crossings_road`: baja/empata 104/108, NUNCA sube (calle real limpiada); sobre cuerdas decía ×2,9–×5,3
- **Alcance sin corrección**: Ciclos #194–#237 (todo anterior a #240)
- **Ciclos con corrección**: #240/#241 (miden ambas), #242/#243/#244 (usan `crossings_road` como primaria)
- **Impacto máximo**: #209 ("2-opt empeora ×8") era artefacto de dibujo; #196 idem
- **Candidatos para re-juicio**: Ciclos cuyo rechazo fue **única o primariamente por cruces**

### D-d: Compuerta de balance viejo ≥0,80
- **Contexto**: Track Q (#185) juzgó con balance ≥0,80; Track M estándar es ≥0,60
- **Redescubrimiento**: F44 (2026-07-24)
- **Alcance**: No afecta a Track M directamente (usa ≥0,60); **sí afecta a ciclos que citan a #185** (p.ej., `exempt-last`)
- **Cambio medido en #185 ahora**: `tmin-scaled+exempt-last` falla 4/12 con balance ≥0,80; **falla 0/12 con ≥0,60**
- **Efecto en M20/M22**: Re-abre `exempt-last` para medición nueva

### D-e: Degeneración por conteo de paradas (<5 paradas)
- **Contexto**: Criterio absoluto `<5 paradas O <1 800 s` mata "rutas degeneradas"
- **Problema**: Una ruta de 3 paradas y 10 485 s es 97 % de T_max — para censista es jornada completa, no turno mutilado
- **Redescubrimiento**: F44 (2026-07-24)
- **Cambio de criterio**: Se **ELIMINA** `<5 paradas` del criterio obligatorio (decisión Alberto 2026-07-24)
- **Alcance**: Ciclos que reportan `degenerate_routes` (desde #219)
- **Efecto medido**: De 104 filas con `degenerate_routes>0`, **43 absueltas** (solo por conteo); 61 siguen por duración
- **Ciclos reabiertos**: `no-floor` NO (dur_min=120 s); `feasible-floor-b095` SÍ (17 filas dur_min 6759–8475 s, pasa a 7/8)

---

## 2. Matriz de auditoría: 16 ciclos × 5 defectos

| Ciclo | PR | Reportaje | D-a | D-b | D-c | D-d | D-e | **Veredicto** | **Cambio en auditoría** |
|---|---|---|---|---|---|---|---|---|---|
| M1a | #194 | objective-audit-postpass-sweep | ✓ falsas | ✓ vieja | ✓ proxy | — | ✓ conta | CONFIAB. BAJA: rechazo por travel/balance en métrica defectuosa | **NO**: doblemente rechazado (travel ≤+3% pero +5,8% en #194); D-a/D-b no lo reviven |
| M1b | #196 | route-config-algorithm-sweep (2-opt) | ✓ falsas | ✓ vieja | ✓ proxy (×8 era dibujo) | — | ✓ conta | RECHAZADO: "2-opt empeora ×8" | **SÍ**: F40 prueba que ×8 sobre cuerdas era artefacto; sobre `crossings_road` baja 12/12. Rechazazo CAUSAL en D-c |
| M1c | #203 | arc convex | ✓ falsas | ✓ vieja | ✓ proxy | — | ✓ conta | RECHAZADO: cruces no son arcos largos | **NO**: rechazo por lógica de causalidad (los cruces ≠ arcos), no por métrica cuerdas en sí; D-c no invalida la premisa |
| M2 | #209 | no-floor-balance-sweep | ✓ falsas | ✓ vieja | ✓ proxy (inverso en n=1607) | — | ✓ conta | RECHAZADO: sin piso cruces +2× y degeneración | **SÍ**: rechazo por D-c + D-e. D-c: sobre calle real `no-floor` es peor (road 73 > actual 43) pero F40 lo somete a doble lectura; D-e: 43/104 filas absueltas. Re-juzgado en M22 con D-e nuevo |
| M4 | #215 | no-floor-balance-sweep | ✓ falsas | ✓ vieja | ✓ proxy | — | ✓ conta | RECHAZADO: piso PARADAS falla balance ≥0,60 | **NO**: rechazo por balance (D-d no aplica a Track M), no depende de D-c |
| M5 | #217 | combined-floor-sweep | ✓ falsas | ✓ vieja | ✓ proxy | — | ✓ conta | RECHAZADO: piso COMBINADO idem; area-26 piso inactivo | **NO**: el descarte de F19 (piso factible ≤k; viaja hasta M22) es aritmética pura, no depende de D-c |
| **M6** | **#221** | **penalty-sensitivity (re-corrida)** | ✅ FIX | ✅ FIX | — | — | — | **CORRECCIÓN DE INSTRUMENTO** (D-a + D-b) | **PUNTO DE CORTE**: 14/28 celdas re-juzgadas; semillas reales; métrica MSF. F20/F21 son el diagnóstico del ciclo. Aquí se calibra la medición |
| M8 | #227 | multistart-sweep | — | — | ✓ proxy | — | ✓ conta | RECHAZADO: multi-arranque empate total, no mata varianza | **NO**: el rechazo es por lógica (N arranques muestrean el mismo punto a T=120 s), no por métrica; D-c no invalida la premisa |
| M10 | #228 | penalty-sensitivity (re-corrida) | — | — | ✓ proxy | — | ✓ conta | RECHAZADO: degeneración estructural (b095 ruta de 3 paradas aisladas) | **SÍ (parcial)**: D-e absuelve 43 filas pero b095 persiste por duración (10 485 s). El "rompe balance" falla con balance ≥0,60 (D-d contexto). Re-evaluar en M22 |
| M9 | #231 | [TSP anchor — reporte menor] | — | — | — | — | — | CIERRE: brecha MSF↔UB 13–29 %, no cambia veredictos | **NO**: es resultado de calibración (M9 es post-#221), no sufre D-a/D-b; no mide cruces |
| M7 | #237 | cluster-constrained-search | — | — | ✓ proxy | — | ✓ conta | RECHAZADO (ambos brazos falsados): clusters blandos ABANDONA árboles; warm start peor geometría | **NO**: los descartes son por lógica (abandono > métrica) y por geografía (3 árboles aislados → ruta stub es universal); D-c no invalida |
| **M16** | **#240/#241** | **crossing-metric-validation** | — | — | ✅ MIDE D-c | — | — | **CORRECCIÓN DE MÉTRICA**: construye `crossings_road`, valida contra calle real; ρ=0,527; signo 2-opt: 104/108 baja/empata | **PUNTO DE CORTE**: D-c se dimensiona y se valida. Replicado en #242: ρ=−0,618 en n=1607 |
| M12×M13 | #242 | floor-price-upper-target | — | — | ✅ usa D-c medida | — | — | RECHAZADO `upper-tmax`: cuerdas −93 % BUT `crossings_road` +42 %; balance 0,723; degenerada 2/3 semillas | **VALIDACIÓN**: M16 necesario y suficiente. `upper-tmax` fue "ganadora rotunda" leyendo solo cuerdas; `crossings_road` lo refuta. F41b citable |
| M19 | #243 | regime-guard | — | — | — | — | — | RECHAZADO: predicado `rho_pad` 3/12 vs 8/12 trivial; no predice ganador | **NO**: es un resultado negativo de método bien ejecutado (pre-registro, doble lectura, salvaguardas). F42 es citable como es |
| M17 | #244 | arc-weight-crossings | — | — | ✅ usa D-c medida | — | — | RECHAZADO: arco peso lineal en n=1607 −20 % pero solo donde travel holgado; regime-dependent | **NO**: resultado negativo medido correctamente con `crossings_road`. F45 es fuerte |
| **M23** | **#245** | **postpass-default** | — | — | ✅ usa D-c medida | — | — | ✅ **ADOPCIÓN**: travel baja 12/12, `crossings_road` baja 12/12; k e balance invariantes; mejora Pareto | **CITABLE**: es el PRIMER cambio de default y vino por M16 (corrección de método). F46 es de primer orden |

---

## 3. Ciclos cuyo veredicto cambia bajo la auditoría

### 3.1 M1b (#196) — 2-opt intra-ruta: veredicto REVISABLE

**Escenario anterior (F35)**: "2-opt empeora autocruces ×2,9–×5,3 sobre base limpia; la métrica de cuerdas es lo que se optimiza"

**Hallazgo M16 (#240/#241)**: El 2-opt minimiza tiempo de red OSRM (`matrix[a][b]`), no cuerdas. La métrica `self_crossings` cuenta cuerdas rectas; el re-secuenciamiento fabricaba cruces falsos entre las nuevas cuerdas.

**Prueba decisiva** (F40): Signo del post-pass sobre `crossings_road` (calles reales):
- 104/108 filas: baja o empata (media −24 % a −45 %, nunca sube)
- 0 casos de suba

**Verdict original** (línea #209): Rechazo por cruces ×8 sobre base limpia. Métrica: `crossings` de cuerdas.

**Re-juicio**: 
- Si `crossings_road` es la métrica autorizada (F40 lo valida), el 2-opt **LIMPIA la calle real**
- La base limpia de #196 se midió con cuerdas; las replicas del 2-opt también
- El ×8 es ARTEFACTO: las cuerdas re-secuenciadas fabrican cruces donde la calle real mejora
- El "mejor candidato en viaje" era `no-floor+reseq` (F30: −48,8 s con travel −8,4 % vs +35,5 %), pero muere por degeneración y balance

**Cambio documentado**: NO se revive el 2-opt como default global. **Pero el rechazo "empeora cruces" queda IMPUGNADO por D-c medida**. El veredicto de #196 deja de ser "rechazado por cruces" y pasa a ser "rechazo por degeneración + balance, las cruces no fueron el problema".

---

### 3.2 M2 (#209) — Sin piso: veredicto PARCIALMENTE IMPUGNADO

**Veredicto original**: Rechazado; cruces +2× vs `actual`; degeneración; balance bajo.

**Auditoría**:
- D-c: Las cuerdas de `no-floor` en n=1607 son artefacto (F40 indica inversión −0,575). Pero `no-floor` ya se re-juega con `crossings_road` en #240 como brazo de contraste.
- D-e: 43/104 filas con degeneración eran solo por conteo; `no-floor` de esas puede sobrevivir re-juicio

**Re-juzgado en M22** (futuro): `no-floor` con D-e nuevo probablemente siga rechazado (dur_min = 120 s, falla de todas formas; balance también falla).

**Cambio documentado**: Las cruces de #209 (el ×2×) son **parcialmente artefacto de D-c**. La degeneración es real. La conclusión "sin piso hay demasiada geometría" se sustituye por "sin piso hay relleno defectivo + balance roto".

---

### 3.3 M10 (#228) — Sensibilidad de piso: veredicto PARCIALMENTE IMPUGNADO

**Veredicto original**: Rechazado; `b095` (ruta de 3 paradas, 10 485 s) es degenerada por conteo.

**Auditoría**:
- D-e: El criterio `<5 paradas` lo mata. Pero es 97 % de T_max (jornada completa). **43/104 filas absueltas por D-e**
- **Sin embargo**: `b095` tiene dur_min 10 485 s; falla también el nuevo criterio de duración (<1 800 s falsa; b095 la cumple)
- D-d: Balance era ≥0,60 (cumple con Track M); no aplica

**Re-juzgado en M22**: `b095` persiste rechazado por duración + falta de relleno (F26 + F29), **no por conteo de paradas**. Pero el costo de *describir* por qué la ruta es degenerada cambia.

**Cambio documentado**: La degeneración de b095 es **estructura territorial** (3 árboles aislados) + T_max, **no conteo de paradas**. El descarte sigue en pie, pero por razón distinta (F26 citable, F39 refuerza geografía).

---

### 3.4 M12×M13 (#242) — Upper en T_max: veredicto REFUTADO

**Veredicto original de celda `upper@T_max + piso 7200`**: 
- Cuerdas: −93 % en n=1607 (pasaría)
- Leyendo solo `crossings` parecería ganadora rotunda

**Hallazgo M16 (#240/#241)**: D-c es proxy parcial (ρ=0,527) e invertido en n=1607 (−0,575)

**Re-juicio con `crossings_road` (#242)**:
- `crossings_road` en n=1607: **+42 %** (41,0 → 58,3), no −93 %
- Balance 0,849 → 0,723 (falla ≥0,60 marginalmente)
- Ruta degenerada (nuevo criterio) en 2/3 semillas (de duración < 1 800 s si se cuenta como antes)
- Áreas: falla relleno (area-26 −25 %, area-29 −0,6 %)

**Veredicto M16-corregido**: REFUTADO. El candidato que las cuerdas hacían ganadora **es rechazado por `crossings_road`**. F41b es citable; **M16 fue necesario**.

**Cambio documentado**: **Crítico**. Sin M16 (D-c medida), este ciclo habría cerrado con "upper@T_max refutada por cuerdas −93 %" (verdad), cuando la verdad es "cuerdas son proxy invertido; la calle real empeora +42 %". Justificación a posteriori de M16.

---

### 3.5 M23 (#245) — Postpass 2-opt como default: veredicto CITABLE

**Veredicto original (de #196/#209)**: 2-opt rechazado; empeora cruces ×8

**Corrección M16 (#240/#241)**: D-c se mide; ×8 era artefacto de cuerdas

**Re-evaluación M23 (#245)**:
- Línea base n=1607 re-corrida con semillas REALES (Fix D-a)
- Travel 59 898 → 58 351 s (−2,6 %)
- k e balance invariantes
- Todas 12 instancias: travel baja; `crossings_road` baja
- Mejora de Pareto (no intercambio)

**Veredicto**: **ADOPCIÓN de default** (primer cambio en 16 ciclos). No es ganador de un barrido; es **corrección de método → costo capitalizado**.

**Cambio documentado**: M23 es **el remate natural de la auditoría**:
1. #221: Auditoría arreglando D-a/D-b → cambió 14/28 veredictos
2. #240/#241 (M16): Auditoría dimensionando D-c → validó que ×8 era dibujo
3. #245 (M23): Adoptando lo que #196 rechazó incorrectamente → primer default nuevo en la serie
4. **Moraleja**: "Quince ciclos barriendo términos del objetivo no movieron un default; lo movió arreglar el instrumento". F46 es de primer orden de tesis.

---

## 4. Ciclos cuyo veredicto NO cambia

### D-c no es causal en #194, #203, #215, #217, #227, #237
- #194: Rechazo por travel (+5,8 %, falla ≤+3 %); D-c no invalida
- #203: Rechazo por lógica (cruces ≠ arcos largos); D-c no invalida la premisa
- #215: Rechazo por balance; D-c no interviene
- #217: Rechazo por aritmética (piso inactivo en area-26, k factible ≤3); D-c no invalida
- #227: Rechazo por lógica (N arranques muestrean mismo punto a T=120 s); D-c no interviene
- #237: Rechazo por lógica (abandono de árboles, geografía universal); D-c no invalida

### D-e parcialmente pero no revive candidatos
- #228 (`b095`): Absuelto de conteo pero persiste por duración + geografía
- #209 (`no-floor`): Absuelto de conteo pero persiste por balance + relleno defectivo; re-juzgado en M22

### Resultados negativos bien medidos (sin cambio)
- #231 (M9): Cierre de calibración; no sufre D-a/D-b; no mide cruces
- #243 (M19): Resultado negativo; pre-registrado; salvaguardas cumplidas → F42 es publicable
- #244 (M17): Resultado negativo; medido con `crossings_road` calibrada → F45 es fuerte

---

## 5. Síntesis: Qué cambió en esta auditoría

| Categoría | Ciclos | Efecto |
|---|---|---|
| **Veredictos revisables** (D-c rectificado) | #196, #209, #242 | 2-opt/no-floor/upper-tmax: el descarte leyendo cuerdas era artefacto; sobre calle real la métrica es distinta |
| **Veredictos que persisten** | #194, #203, #215, #217, #227, #237 | Rechazos no dependen de D-c; D-a/D-b tampoco los reviven (doblemente rechazados o premisas lógicas) |
| **Veredictos reabiertos por D-e** | #228, #209 | Se absuelven filas por conteo; la conclusión persiste (degeneración por duración o balance) |
| **Correcciones de instrumento** | #221 (D-a/D-b), #240/#241 (D-c) | Cambiaron la medición; #221 cambió 14/28 veredictos; #240/#241 validó que ×8 era dibujo |
| **Primer cambio de default** | #245 (M23) | Citable porque vino por M16; justificado a posteriori |

---

## 6. Limitaciones para la tesis (§3.1.4)

Este ciclo documenta **cuatro hallazgos de ciencia que quedan para la discusión**:

1. **D-a (semillas falsas)**: Las mediciones previas a julio 2026 (#194–#217) corrieron con n=1 disfrazado de n=3. La varianza reportada σ ≈0,03 % es artefacto de replicación idéntica, no convergencia del solver. Implicación: ningún ciclo anterior se apoya en barras de error confiables. La serie **auditándose a sí misma** descubrió el defecto (F20) y lo corrigió (#221), capturando 14/28 re-juicios como cambio de medición.

2. **D-c (cuerdas vs calles)**: La métrica de autocruces sobre cuerdas rectas entre paradas es un proxy parcial (ρ Spearman 0,527) de la geometría real, e invertida en la instancia insignia (−0,575 en n=1607, −0,618 en réplica). Implicación: todo lo anterior a M16 (#240/#241) que fue rechazado **únicamente por cruces** está bajo revisión; lo que fue **aceptado gracias a cruces** (candidato: `upper-tmax`) resulta refutado al medir con `crossings_road`. La serie audita su propia métrica y descubre que el "2-opt empeora ×8" era artefacto de dibujo; sobre la calle real el 2-opt limpia la geometría en 104/108 casos.

3. **D-e (paradas vs duración)**: El criterio de "ruta degenerada" (`<5 paradas O <1 800 s`) mezcla un proxy de aislamiento geográfico (paradas) con perjuicio operativo verdadero (duración). Recalibración (julio 2026): se elimina el conteo de paradas; de 104 filas que violaban el viejo criterio, 43 quedan absueltas (solo eran por conteo); 61 persisten por duración. Implicación: ruta `b095` (3 paradas, 10 485 s = 97 % de T_max) deja de ser "degenerada" en la nominación (es jornada completa para censista), pero no se revive en el veredicto (falla balance, relleno, y geografía que F39 mostró universal).

4. **Moraleja metodológica**: En 16 ciclos y seis meses, las correcciones más impactantes vinieron de **arreglar instrumentos** (D-a, D-b en #221 → 14/28 veredictos; D-c medida en #240/#241 → refuta `upper-tmax`), no de barrer configuraciones. El primer default que cambió (#245, M23) fue por capitalizar la corrección de D-c. La serie no solo cierra con una ganadora verificada; cierra documentando cómo se auditó a sí misma y qué aprendió de sus propios defectos.

---

## 7. Cambios de criterio registrados

**F44 (2026-07-24)**: Eliminada cláusula `<5 paradas` del criterio de aceptación. Razón: conteo de paradas es proxy de aislamiento geográfico, no perjuicio operativo; F26 + F39 probaron que la ruta stub la reproduce cualquier método que respete geografía. **Solo degeneration_by_duration queda activo** (< 1 800 s). Efecto: de 104 filas con `degenerate_routes>0`, 43 absueltas; 61 persisten.

Ciclos afectados:
- M1–M10 (#194–#228): Reportan la vieja cifra; re-juzgado en M22 con nuevo criterio
- M9, M16+: Usan una u otra métrica; declarar explícitamente en reportes

---

## Apéndice: Referencias a CSVs y reportes versionados

- `20260713-real-case-metrics-spatial.csv` — línea base n=1607 original (M1, pre-postpass)
- `20260724-213512-postpass-baseline.csv` — línea base n=1607 post-M23 (con semillas reales)
- `docs/experiments/objective-audit-postpass-sweep-20260718.md` — M1a (#194)
- `docs/experiments/route-config-algorithm-sweep-20260718.md` — M1b (#196)
- `docs/experiments/no-floor-balance-sweep-20260719.md` — M2/M4 (#209, #215)
- `docs/experiments/combined-floor-sweep-20260720.md` — M5 (#217)
- `docs/experiments/penalty-sensitivity-20260713.md` — M6 (#221, re-corrida)
- `docs/experiments/multistart-sweep-20260721.md` — M8 (#227)
- `docs/experiments/penalty-sensitivity-20260713.md` [reporte 2] — M10 (#228, re-corrida)
- `docs/experiments/cluster-constrained-search-20260722.md` — M7 (#237)
- `docs/experiments/crossing-metric-validation-20260723.md` — M16 (#240/#241)
- `docs/experiments/floor-price-upper-target-20260723.md` — M12×M13 (#242)
- `docs/experiments/regime-guard-20260724.md` — M19 (#243)
- `docs/experiments/arc-weight-crossings-20260724.md` — M17 (#244)
- `docs/experiments/postpass-default-20260724.md` — M23 (#245)

---

**Conclusión**: La serie Track M audita sus propias evidencias. De los 16 ciclos, 3 tienen veredictos revisables por D-c medida (#196, #209, #242); 2 son correcciones de instrumento (#221, #240/#241); 1 es un default nuevo justificado a posteriori (#245). Los restantes 10 ciclos producen resultados negativos bien fundamentados. La auditoría no invalida comparaciones relativas (misma vara en todos), pero sí aclara el nivel absoluto y expone las limitaciones de la métrica de cuerdas. **Esto es material de defensa de primer orden**: es la serie auditándose a sí misma.
