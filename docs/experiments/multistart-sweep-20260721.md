# Multi-arranque: ¿se puede matar la cola de la distribución?

**Fecha:** 2026-07-21
**Estado:** pre-registro. Esta sección (diseño + criterio + umbrales) se commitea **antes** de
mirar ningún resultado. Los resultados se agregan después, sin tocar el criterio.

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual, coeficiente de
span espacial 3) intactos, y el multi-arranque es opt-in por flag (`--starts`, `--budget`). Con
`--starts 1` el pipeline llama exactamente al mismo camino de código que antes.

---

## Por qué este ciclo

El ciclo anterior (`sweep-metrology-20260720.md`) cerró la familia de brazos de piso con veredicto
limpio: `feasible-floor-b095` pasa **7 de 8** criterios y falla uno solo, **1 ruta degenerada en 1
de 5 semillas**. Sus fallos son de **cola, no de media**: 0 instancias con balance <0.60 en
promedio, 2 en la peor semilla.

Ese reporte dejó escrita la hipótesis que este ciclo mide, y dijo explícitamente que **no** la
midió: resolver con varias semillas y quedarse con la mejor, ahora que las semillas por fin son
réplicas reales (permutación del orden de nodos; OR-Tools no expone RNG, verificado en los tres
protos).

**Hipótesis a falsar:** el multi-arranque elimina la cola —0 rutas degeneradas y balance ≥0.60 en
**todas** las réplicas— sin degradar la media. Si `b095` + multi-arranque pasa el criterio
**completo** de la serie, es la primera ganadora verificada.

---

## Diseño

### 1. La corrida ganadora se elige por el objetivo del solver

Entre los `N` arranques se conserva el de **menor `objective_ortools`**, y nada más. Elegir por
"menos cruces" o "mejor balance" sería **seleccionar sobre el criterio de aceptación**: el
multi-arranque se convertiría en un maximizador de la métrica que después se usa para juzgarlo, y
el veredicto quedaría contaminado por construcción. La regla queda escrita aquí, antes de medir, y
está implementada en un solo lugar (`apps/optimization/multistart.py`).

Consecuencia aceptada de antemano: es posible que el multi-arranque **no** mejore los cruces ni el
balance, porque no los está optimizando. Ese resultado, si aparece, es un hallazgo del ciclo y se
reporta como tal.

### 2. Dos lecturas de presupuesto, y las dos se reportan

| Brazo de presupuesto | Tiempo por arranque | Wall-clock | Qué contesta |
| --- | --- | --- | --- |
| **(a) fijo por arranque** | `T` completo cada uno | `N × T` | ¿La mejor de N corridas completas mata la cola? |
| **(b) total fijo** | `T / N` cada uno | `T` | ¿La mata **gratis**, sin gastar más cómputo? |

`T = min(30 + 1.5·n, 120)` s, la misma configuración censal de referencia de toda la serie.

El brazo **(b) no es opcional**. El multi-arranque mejora el mejor caso *por construcción*: tomar
el mínimo de N muestras de la misma distribución no puede empeorar, así que comparar N=5 contra
N=1 a igual tiempo **por arranque** es una comparación injusta a favor del brazo nuevo. (b) es el
único contraste honesto, porque iguala el cómputo total y obliga a cada arranque a converger
menos.

**Y es la pregunta más interesante del ciclo:** si (b) también mata la cola, el multi-arranque
sale gratis y la conversación de adopción cambia por completo — deja de ser un intercambio
"5× cómputo por estabilidad" y pasa a ser una mejora sin costo. Se responde **explícitamente** en
el reporte, pase lo que pase.

### 3. Brazos, instancias y réplicas

- **Configuraciones:** `actual` (control de producción) y `feasible-floor-b095` (candidato).
- **N ∈ {1, 3, 5}**. Con N=1 los dos presupuestos coinciden, así que se corre una sola vez y se
  reporta en ambas lecturas. Arms efectivos por configuración: `n1`, `n3-per-start`,
  `n5-per-start`, `n3-total`, `n5-total`.
- **12 instancias congeladas:** batería {50, 100, 200, 400, 800, 1000}, dispersas {250, 500},
  áreas reales {157, 72, 43} y `reference-n1607`.
- **5 réplicas externas.** La semilla externa siembra el **conjunto** de arranques
  (`start_seeds(seed, N)`), no un arranque suelto: lo que se mide es la varianza de la
  **política**, no la de una corrida dentro de ella. Los conjuntos son **anidados**: los N=3
  arranques de una semilla son los tres primeros de sus N=5, así que N es una escalera y no cinco
  sorteos sin relación.

Total: 2 configuraciones × 5 arms × 12 instancias × 5 semillas = **600 filas**; en cómputo,
`2 × 12 × 5 × (1+3+5+1+1) = 1 320` unidades de `T`.

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s |
| T_max | 10 800 s |
| T_min | 7 200 s |
| Límite de tiempo del solver | `T = min(30 + 1.5·n, 120)` s |
| Semillas externas | 1–5 |

---

## Criterio — heredado, no renegociable a posteriori

Idéntico al de los cinco ciclos previos. No se reescribe ningún umbral en este ciclo.

- **`reference-n1607`:** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** `relleno_msf` **−≥30 %** vs `actual`; cruces **sin empeorar**.
- **Global:** **0 drops**; **balance ≥0.60** en **toda** instancia; **0 rutas degeneradas**, con
  la definición absoluta de siempre (**<5 paradas** O **<1 800 s**).

**Regla de varianza.** Una diferencia entre brazos cuenta como **real** sólo si
`|media_A − media_B| > desv_A + desv_B` sobre las 5 réplicas. Si no la supera, se reporta como
**empate**, con esa palabra. Los criterios se evalúan sobre la media de las 5 réplicas; el balance
y las rutas degeneradas se reportan **además** por peor réplica, porque la hipótesis de este ciclo
es precisamente sobre la cola: un piso que sólo se cumple en promedio no es un piso.

**Qué contaría como confirmación de la hipótesis:** `b095` con multi-arranque, **0 rutas
degeneradas en las 60 filas** del arm (12 instancias × 5 réplicas) y **balance ≥0.60 en toda
instancia y toda réplica**, sin que travel ni cruces se degraden más allá de la regla de varianza.
Cualquier cosa menos que eso es un fallo del criterio y se reporta como fallo.

## Riesgo declarado

1. El multi-arranque **no puede empeorar** el objetivo del solver por construcción; que mejore el
   objetivo **no** es un hallazgo. El hallazgo es qué le pasa a la cola de las métricas de
   criterio, que el solver no optimiza.
2. La selección por objetivo del solver puede dejar el criterio **sin mover**: el mínimo de N
   objetivos no es el mínimo de N conteos de rutas degeneradas. Se acepta de antemano.
3. Si el resultado es negativo se reporta **igual de fuerte** que uno positivo.
4. `wall_clock_sec` no es comparable con ciclos previos ni entre arms: las celdas corren en
   flujos paralelos sobre la misma máquina y el límite del solver es de reloj, así que la
   contención de CPU reduce iteraciones de GLS. Es exactamente lo que las barras de error miden.
   Para el costo del brazo (a) se reporta el **número de arranques**, que es la magnitud
   estructural, no el wall-clock medido.

---

## Reproducción

```bash
# Un CSV por arm y por réplica; el driver es reanudable (salta las filas ya escritas).
for cell in actual feasible-floor-b095; do
  for seed in 1 2 3 4 5; do
    # N=1 (los dos presupuestos coinciden)
    docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
      python manage.py config_algorithm_sweep \
        --csv "docs/experiments/multistart-sweep-20260721-$cell-n1-s$seed.csv" \
        --only-cell "$cell" --seeds "$seed" --starts 1 --budget per-start
    # N ∈ {3,5} × presupuesto ∈ {per-start, total}
    for starts in 3 5; do
      for budget in per-start total; do
        docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
          python manage.py config_algorithm_sweep \
            --csv "docs/experiments/multistart-sweep-20260721-$cell-n$starts-$budget-s$seed.csv" \
            --only-cell "$cell" --seeds "$seed" --starts "$starts" --budget "$budget"
      done
    done
  done
done
```

Los CSV por réplica se concatenan en un CSV por arm,
`multistart-sweep-20260721-<cell>-<arm>.csv`, que es lo que se publica junto a este reporte.
