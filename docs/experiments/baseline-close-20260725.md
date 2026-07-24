# Cierre de deuda M25: re-corrida de línea base con semillas reales

**Fecha:** 2026-07-25  
**Estado:** Cierre de deuda M25 dejada por PR #245 — exactitud de tesis.

---

## 1. Contexto y deuda

PR #245 (M23, 2026-07-24) adoptó el post-pass 2-opt como default del pipeline y re-corrió la línea base de referencia-n1607, pero dejó la tesis en estado inconsistente:

- §3.1.2 citaba cifras del post-pass (travel 58 351 s)
- §3.1.1 mantenía cifras vieja sin post-pass (travel 59 898 s) para la MISMA corrida
- El párrafo de convergencia de semillas (línea 57–76) publicaba un artefacto: "dispersión 0,03%" y "las 3 semillas convergieron a soluciones prácticamente idénticas"

**El artefacto es F20, defecto de instrumentación cerrado en #221:** las "3 semillas" nunca llegaban al solver (eran 3 copias del mismo número), haciendo parecer determinista lo que en realidad no recibía aleatoriedad. Con el fix, las semillas SÍ varían en el solver.

---

## 2. Re-corrida: cifras medidas

Instancia: **reference-n1607**, parámetros: service 2 min, T\_min=2h, T\_max=3h, solver time_limit 120s, **con post-pass 2-opt habilitado**.

| Semilla | k | Travel (s) | Balance | Route Time Mean (s) | Route Time σ (s) |
|---------|---|-----------|---------|-------------------|------------------|
| 42      | 25 | 59 689.70 | 0.836   | 10 101             | 536               |
| 43      | 25 | 56 707.30 | 0.837   | 9 982              | 529               |
| 44      | 25 | 58 695.80 | 0.829   | 10 061             | 612               |
| **Media**   | **25** | **58 364.27** | **0.834** | **10 048** | **559** |

**Comparación con cifras previas (CSV 20260724-213512-postpass-baseline.csv):**

| Métrica | Anterior (PR #245) | Nuevo (hoy) | Diferencia |
|---------|------------------|-----------|-----------|
| Travel medio (s) | 58 351 | 58 364 | +13 s |
| Route time mean (s) | — | 10 048 | — |
| Route time σ (s) | — | 559 | — |

Diferencias < 0.1%, dentro del ruido de re-ejecución (orden de entrada distinto). **Las columnas faltantes (route_time_mean_sec, route_time_std_sec, routes_over_t_max, dropped_trees) ahora están presentes en el comando baseline_postpass.**

---

## 3. Actualización de tesis: líneas y cambios

| Sección | Línea | Cambio | Razón |
|---------|------|--------|-------|
| §3.1.1 Tab 1 | 39 | 10 110 s → 10 048 s | Media medida de 3 semillas |
| §3.1.1 Tab 1 | 40 | 519 s → 559 s | σ de duración de ruta (5.1% → 5.5%) |
| §3.1.1 Párrafo convergencia | 57–76 | Reescrito | F20: dispersión real ~5%, no 0,03% |
| §3.1.1 Texto | 136 | 58 351 s → 58 364 s | Media de re-corrida actual |
| §3.1.2 Tab 2 | 172 | 58 351 s → 58 364 s | Consistencia con §3.1.1 |
| §3.1.2 Tab 2 | 174 | 519 s → 559 s | σ de duración |
| §3.1.2 Nota | 180–181 | Ahorro −6.3% → −6.7% | Aritmética verificada: 4 221 / 62 585 |
| §3.1.2 Texto | 185 | 10 110 s (93,6%) → 10 048 s (93,0%) | Saturation medida |

---

## 4. Lectura de F20: defecto de instrumentación en la serie previa

El párrafo original (línea 57–76 previo) argumentaba:

> "Las tres repeticiones agotaron el presupuesto completo de 120s del metaheurístico GLS y convergieron a soluciones prácticamente idénticas: los tres valores de k, de balance y de desviación estándar coinciden, y el tiempo total de desplazamiento difiere en 19s entre la mejor y la peor repetición (59 911s, 59 892s y 59 892s; media 59 898s), esto es, un 0.03% de dispersión. La semilla solo etiqueta la repetición: ni global ni spatial_term consumen aleatoriedad […] el solver de OR-Tools es determinista dados sus parámetros de entrada."

Este párrafo fue correcto en su descripción mecánica, **pero publica un síntoma de F20, no un hallazgo verdadero:** la dispersión de 0,03% NO reflejaba el comportamiento del solver, sino que las "3 semillas" nunca llegaban a él. El comando que generó ese CSV (baseline_sweep, #185) no pasaba `node_seed` al pipeline.

**Cambio en la re-corrida de hoy:**
- Comando baseline_postpass.py SÍ pasa `node_seed=seed` al pipeline
- Las 3 semillas ahora se diferencian por permutación del orden de entrada
- Eso propaga a soluciones distintas: travel 56 707–59 690 s (dispersión ~5%, coef. variación ~1%)

**Lectura corregida:** Las réplicas se construyen permutando el orden de entrada de nodos. El solver OR-Tools es determinista a orden fijo, pero el orden de nodos —irrelevante matemáticamente— es suficiente para generar trayectorias del GLS distintas. La dispersión anterior era artefacto de no pasar la semilla. La dispersión actual (~5%) refleja sensibilidad real al orden de entrada.

---

## 5. Verificaciones

✓ Instrumento: baseline_postpass.py ahora emite route_time_mean_sec, route_time_std_sec, routes_over_t_max, dropped_trees.

✓ Cifras verificadas contra CSV generado: `docs/experiments/20260724-225420-postpass-baseline.csv`.

✓ Aritmética verificada (ahorro contra greedy): (62 585 − 58 364) / 62 585 = 6.74% ≈ −6.7%.

✓ Tesis compilable: `make -C docs/thesis/` pasa sin errores.

✓ Jobs limpiados: 3 OptimizationJob + dependencias deletadas después de medición.

---

## 6. Archivos generados

- `backend/apps/optimization/management/commands/baseline_postpass.py` — Comando actualizado con columnas faltantes (commit en rama docs/m25-baseline-close).
- `docs/experiments/20260724-225420-postpass-baseline.csv` — Re-corrida actual (3 semillas, 3 jobs limpios after).
- `docs/thesis/secciones/03-resultados.tex` — Actualizado con cifras medidas y lectura correcta de F20.
- `docs/experiments/postpass-default-20260724.md` — Typo corregido (julio 2026).

---

## 7. Cierre

La deuda M25 consistía en completar la re-corrida de línea base dejada por #245 y corregir la tesis. Las secciones 3.1.1 y 3.1.2 ahora son consistentes entre sí y con los datos medidos. El párrafo de convergencia de semillas fue reescrito con la lectura correcta del defecto F20, reconociendo la dispersión real (~5%) en lugar de publicar el artefacto de 0,03% que refleja falta de pase de semilla al solver.

No hubo cambio de configuración: post-pass sigue habilitado (default desde #245). El instrumento fue completado, la tesis fue corregida.
