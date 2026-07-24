# Cierre de deuda M25: re-corrida de línea base con semillas reales

**Fecha:** 2026-07-24  
**Estado:** Cierre de deuda M25 dejada por PR #245 — exactitud de tesis.

---

## 1. Contexto y deuda

PR #245 (M23, 2026-07-24) adoptó el post-pass 2-opt como default del pipeline y re-corrió la línea base de reference-n1607, pero dejó la tesis en estado inconsistente:

- §3.1.2 citaba cifras del post-pass (travel 58 351 s)
- §3.1.1 mantenía cifras viejas sin post-pass (travel 59 898 s) para la MISMA corrida
- El párrafo de convergencia de semillas publicaba un artefacto: "dispersión 0,03%" y "las 3 semillas convergieron a soluciones prácticamente idénticas"
- Varias cifras derivadas quedaron colgadas de la corrida vieja: el ahorro contra greedy (4,3%), la diferencia entre corridas (1,2%) y la procedencia de los datos crudos (comando y CSV de la corrida de 2026-07-13)

**El artefacto es F20, defecto de instrumentación cerrado en #221:** las "3 semillas" de la corrida de 2026-07-13 nunca llegaban al solver (eran 3 copias del mismo número), haciendo parecer determinista lo que en realidad no recibía perturbación. El comando que generó ese CSV (`baseline_sweep`, #185) no pasaba `node_seed` al pipeline.

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

Diferencia < 0,1%, dentro del ruido de re-ejecución (orden de entrada distinto). **Las columnas faltantes (`route_time_mean_sec`, `route_time_std_sec`, `routes_over_t_max`) ahora las emite `baseline_postpass`**; el conteo de descartes ya estaba presente como `drops` y no se duplica.

---

## 3. Actualización de tesis

| Sección | Cambio | Razón |
|---------|--------|-------|
| §3.1.1 Tabla 1 | 10 110 s → 10 048 s | Media medida de 3 semillas |
| §3.1.1 Tabla 1 | 519 s → 559 s | σ de duración de ruta (5,1% → 5,5% del promedio) |
| §3.1.1 párrafo de convergencia | Reescrito | Dispersión real 5,1%, no 0,03% |
| §3.1.1 párrafo de sensibilidad | Reescrito | Duplicaba la mecánica del párrafo anterior y citaba el 0,03% ya eliminado |
| §3.1.1 texto | 1,2% → 3,9% | Diferencia contra la corrida de comparación de estrategias (58 364 vs 60 611) |
| §3.1.1 procedencia | `baseline_sweep` / CSV 20260713 → `baseline_postpass` / CSV 20260724-225420 | El comando y el CSV citados no contenían las cifras publicadas |
| §3.1.1 tiempos de cómputo | Atribuidos explícitamente a la corrida de 2026-07-13 | El CSV nuevo no instrumenta tiempos de pipeline |
| §3.1.2 Tabla 2 | 58 351 s → 58 364 s | Consistencia con §3.1.1 |
| §3.1.2 Tabla 2 | 519 s → 559 s | σ de duración |
| §3.1.2 nota | Ahorro −6,3% → −6,7% | Aritmética verificada: 4 221 / 62 585 |
| §3.1.2 texto | 10 110 s (93,6%) → 10 048 s (93,0%) | Saturación medida |
| §3.1.2 texto | 4,3% → 6,7% | Misma cifra de ahorro que la nota de la tabla |

---

## 4. Lectura de F20: defecto de instrumentación en la serie previa

El párrafo original argumentaba:

> "Las tres repeticiones agotaron el presupuesto completo de 120s del metaheurístico GLS y convergieron a soluciones prácticamente idénticas: los tres valores de k, de balance y de desviación estándar coinciden, y el tiempo total de desplazamiento difiere en 19s entre la mejor y la peor repetición (59 911s, 59 892s y 59 892s; media 59 898s), esto es, un 0.03% de dispersión. La semilla solo etiqueta la repetición: ni global ni spatial_term consumen aleatoriedad […] el solver de OR-Tools es determinista dados sus parámetros de entrada."

Este párrafo fue correcto en su descripción mecánica, **pero publica un síntoma de F20, no un hallazgo verdadero:** la dispersión de 0,03% NO reflejaba el comportamiento del solver, sino que las "3 semillas" de esa corrida nunca llegaban a él.

`baseline_postpass` ya pasaba `node_seed=seed` al pipeline desde #245 —la corrida 20260724-213512 muestra tres travel distintos—, de modo que el defecto era del CSV de 2026-07-13 que la tesis seguía citando, no de la instrumentación actual.

**Dispersión medida hoy:** travel 56 707–59 690 s, es decir 2 983 s entre el mejor y el peor resultado (5,1% de la media), con σ = 1 519 s y coeficiente de variación 2,6%.

**Lectura corregida:** Las réplicas se construyen permutando el orden de entrada de nodos. El solver OR-Tools es determinista a orden fijo, pero el orden de nodos —irrelevante matemáticamente— altera el desempate de `PATH_CHEAPEST_ARC` y con ello toda la trayectoria del GLS. La dispersión anterior era artefacto de no pasar la semilla; la actual refleja sensibilidad real al orden de entrada.

---

## 5. Verificaciones

✓ Instrumento: `baseline_postpass.py` ahora emite `route_time_mean_sec`, `route_time_std_sec` y `routes_over_t_max`.

✓ Cifras verificadas contra CSV generado: `docs/experiments/20260724-225420-postpass-baseline.csv`.

✓ Aritmética verificada (ahorro contra greedy): (62 585 − 58 364) / 62 585 = 6,74% ≈ −6,7%.

✓ Tesis compilable: `make -C docs/thesis/` pasa sin errores.

✓ Jobs limpiados: 3 OptimizationJob + dependencias eliminadas después de la medición.

---

## 6. Archivos tocados

- `backend/apps/optimization/management/commands/baseline_postpass.py` — Comando actualizado con las columnas faltantes.
- `docs/experiments/20260724-225420-postpass-baseline.csv` — Re-corrida actual (3 semillas, jobs limpiados después).
- `docs/thesis/secciones/03-resultados.tex` — Actualizado con cifras medidas y lectura correcta de F20.
- `docs/experiments/postpass-default-20260724.md` — Typo corregido (julio 2026).

---

## 7. Cierre

La deuda M25 consistía en completar la re-corrida de línea base dejada por #245 y corregir la tesis. Las secciones 3.1.1 y 3.1.2 ahora son consistentes entre sí y con los datos medidos, y toda cifra derivada (ahorro contra greedy, diferencia entre corridas, procedencia de los datos crudos) apunta a la corrida medida. El párrafo de convergencia de semillas fue reescrito reconociendo la dispersión real (5,1%) en lugar de publicar el artefacto de 0,03%.

No hubo cambio de configuración: post-pass sigue habilitado (default desde #245). El instrumento fue completado, la tesis fue corregida.
