# Barrido de pisos anti-stub: piso de paradas vs piso de tiempo bajo

**Fecha:** 2026-07-20
**Datos:** `stops-floor-sweep-20260720.csv`.

Todo el barrido corre por *overrides* de CLI del driver `config_algorithm_sweep`. La
configuración de producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig`
actual, coeficiente de span espacial 3) intactos. Los brazos nuevos son opt-in.

Este reporte cierra el ciclo abierto por `no-floor-balance-sweep-20260719.md`, cuyo veredicto
fue: quitar el piso de duración logra en n=1607 la mejor geometría medida en toda la serie
(cruces −93 %, travel −13.9 %, relleno −25 %) pero deja **rutas stub** —una ruta de un solo
árbol, balance 0.011— y el span cost global recupera el balance reintroduciendo relleno y
fragmentando las instancias chicas. Su conclusión transversal —"la dirección viva es un piso
suficiente para prohibir stubs pero no para forzar relleno"— es exactamente lo que se prueba
aquí.

---

## Hipótesis

Un piso de **tiempo** es paddeable: caminar en círculos suma segundos, así que el solver puede
satisfacerlo rellenando, y de ahí salen el relleno y los cruces. Un piso de **paradas** no es
paddeable: caminar no suma árboles. La única forma de satisfacerlo es llevarse más nodos, es
decir, no dejar rutas stub.

Si la hipótesis es correcta, un piso de paradas debería conservar la geometría de `no-floor`
(cruces y travel) eliminando a la vez las rutas stub, mientras que un piso de tiempo bajo
—aunque sea absoluto y flojo— debería reintroducir relleno en proporción a su altura.

---

## Registro previo (fijado ANTES de correr — no renegociable a posteriori)

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s (2 min) |
| T_max | 10 800 s (3 h) |
| T_min | 7 200 s (2 h, default de producción; solo lo usan los brazos que lo declaran) |
| Límite de tiempo del solver | heurístico `min(30 + 1.5·n, 120)` s |
| Semillas | 3 por celda |

### Instancias

Batería `{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales
`{157, 72, 43}` y `n=1607`. Cargadas con `load_instances` (UUID estables, cache OSRM acierta).

### Definición de ruta degenerada — CAMBIO respecto al barrido del 19

Una ruta es **degenerada** si tiene **menos de 5 paradas** O una duración **menor a 1 800 s**
(media mañana de trabajo). **Ambos umbrales son absolutos.**

El barrido del 2026-07-19 usaba el segundo umbral *relativo* a la mediana de duraciones de la
propia solución (< 25 % de la mediana). Ese reporte dejó consignada la limitación: una solución
**uniformemente fragmentada** no se detecta, porque ninguna ruta baja del 25 % de una mediana
que ya es enana (`area-29-n43` con span c=1000: 6 rutas de ~16 min, 0 degeneradas marcadas). El
umbral absoluto sí la detecta. El cambio hace las columnas `degenerate_routes` de los dos
barridos **no comparables entre sí**; por eso `actual` y `feasible-floor-b095` se re-corren aquí
en vez de releerse del CSV anterior.

### Criterio de éxito a priori

- **n=1607 (denso saturado):** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** relleno (`relleno_sec`) **−≥50 %** vs `actual`, cruces **sin
  empeorar**.
- **Global:** **0 drops**, **balance min/max ≥0.60** en toda instancia, y **0 rutas
  degeneradas** según la definición absoluta de arriba.
- σ(T) y balance se reportan en todas las celdas aunque el balance ya no sea criterio duro más
  allá del piso de cordura 0.60.
- **Head-to-head final** de la mejor celda contra `feasible-floor-b095` y contra `no-floor`
  puro, ambos medidos en este mismo barrido.

---

## Brazos

Estrategia `spatial_term`, 3 semillas, suite completa de 12 instancias.

| # | Brazo | Mecanismo |
| --- | --- | --- |
| 1 | `actual` (baseline) | Producción: soft lower T_min 10 000/s, soft upper midpoint 500/s. Re-corrido en este barrido para poblar `degenerate_routes` con la definición nueva. |
| 2 | `no-floor` | Sin cotas blandas: soft lower OFF, soft upper en T_max (inerte, la dimensión Time ya lo impone como capacidad dura). Referencia del ciclo anterior, re-corrida. |
| 3 | `no-floor-stops{5,10,15}` | Brazo 2 + dimensión unitaria **Stops** (1 por nodo real visitado, 0 desde/hacia el depot dummy) con `SetCumulVarSoftLowerBound` sobre su cumul final, penalidad 10 000 por parada faltante. **No paddeable.** |
| 4 | `no-floor-lowfloor{3600,5400}` | Brazo 2 pero con soft lower de **Time** en un valor absoluto bajo (1 h / 1,5 h), penalidad 10 000/s. Comparación honesta piso-tiempo-bajo vs piso-paradas. |
| 5 | `feasible-floor-b095` | Re-corrido (no releído): el candidato más cercano del ciclo anterior, ahora con degeneración medida de primera mano. |
| 6 | Grilla de span espacial | Condicional: para la ganadora de los brazos 3–4, coeficiente de span espacial ∈ {3, 10, 30}. El 3 se calibró con el soft lower dominante activo; sin ese piso la escala relativa del término espacial cambia. |

Los vehículos vacíos quedan en cumul 0 en la dimensión Stops y **no pagan** el soft lower
(verificado en `objective-audit-postpass-sweep-20260718.md` para las cotas de Time y
re-verificado aquí en test unitario para Stops: la brecha de objetivo entre `no-floor` y
`no-floor-stops5` es exactamente el déficit de las rutas **activas**).

### Nota de ejecución

Las celdas se corren en varios flujos paralelos sobre la misma máquina. El límite de tiempo del
solver es de reloj, así que la contención de CPU reduce iteraciones de GLS; **todas** las
celdas, incluidos los baselines `actual` y `no-floor`, se corren bajo el mismo esquema, de modo
que la comparación entre celdas es interna y homogénea. Las columnas `wall_clock_sec` y
`t_metaheuristic_sec` no son comparables con las de barridos previos.

---

## Resultados

_(pendiente: se completa al terminar el cómputo)_

---

## Reproducción

```bash
# Una celda por invocación, mismo CSV, resumible
for cell in actual no-floor no-floor-stops5 no-floor-stops10 no-floor-stops15 \
            no-floor-lowfloor3600 no-floor-lowfloor5400 feasible-floor-b095; do
  docker compose -p arbocensus run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv docs/experiments/stops-floor-sweep-20260720.csv --only-cell "$cell"
done

# Grilla de span espacial sobre la celda ganadora (el coeficiente 3 ya salió arriba)
for coef in 10 30; do
  docker compose -p arbocensus run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv docs/experiments/stops-floor-sweep-20260720.csv \
      --only-cell "<ganadora>" --spatial-span-coef "$coef"
done
```
