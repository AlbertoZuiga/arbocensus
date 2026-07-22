# Multi-arranque: ¿se puede matar la cola de la distribución?

**Fecha:** 2026-07-21
**Estado:** cerrado. La sección de diseño y criterio se commiteó **antes** de mirar ningún
resultado (commit `854d9aa`); los resultados se agregaron después, sin tocar el criterio.

**Veredicto en una línea:** el multi-arranque **no mata la cola**. Ni con presupuesto por
arranque (5× cómputo) ni con presupuesto total fijo: bajo la regla de varianza pre-registrada,
las rutas degeneradas y el balance mínimo quedan en **empate** contra N=1 en las dos lecturas, y
el brazo de presupuesto total **rompe** el criterio de travel. La hipótesis queda falsada.

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

## Resultados

Datos: `multistart-sweep-20260721-{actual,feasible-floor-b095}-{n1,n3-per-start,n5-per-start,
n3-total,n5-total}.csv`. **600 filas**: 2 configuraciones × 5 arms × 12 instancias × 5 réplicas
externas. Ninguna celda falló ni quedó incompleta.

El costo del brazo (a) se reporta como el **número de arranques** (1×, 3×, 5×), que es la magnitud
estructural, según el riesgo #4. El wall-clock medio por fila —117 s con N=1, 325 s con N=3, 568 s
con N=5, contra 118–119 s de los dos brazos de presupuesto total— reproduce esa razón porque los
50 flujos corrieron con el mismo grado de paralelismo; no se usa para nada más, y en particular no
se compara con barridos previos ni se lee como diferencia de rendimiento entre arms.

### La pregunta del ciclo: la cola

Rutas degeneradas por réplica (suma sobre las 12 instancias) y balance mínimo de la suite por
réplica:

| Configuración | Arm | Degeneradas por réplica | media ± sd | Balance mínimo por réplica | media ± sd |
| --- | --- | --- | ---: | --- | ---: |
| `actual` | `n1` | 0, 0, 0, 0, 0 | 0.0±0.0 | 0.836 / 0.814 / 0.832 / 0.814 / 0.822 | 0.824±0.009 |
| `actual` | `n3-per-start` | 0, 0, 0, 0, 0 | 0.0±0.0 | — | 0.828±0.013 |
| `actual` | `n5-per-start` | 0, 0, 0, 0, 0 | 0.0±0.0 | — | 0.826±0.009 |
| `actual` | `n3-total` | 1, 1, 0, 0, 0 | 0.4±0.5 | — | 0.827±0.006 |
| `actual` | `n5-total` | 0, 0, 0, 0, 0 | 0.0±0.0 | — | 0.830±0.005 |
| **`b095`** | **`n1`** | **1, 0, 1, 1, 0** | **0.6±0.5** | 0.644 / 0.660 / 0.652 / 0.652 / 0.618 | **0.645±0.015** |
| `b095` | `n3-per-start` | 1, 0, 1, 1, 1 | 0.8±0.4 | 0.633 / 0.619 / 0.652 / 0.582 / 0.592 | 0.616±0.026 |
| `b095` | `n5-per-start` | 1, 0, 1, 1, 1 | 0.8±0.4 | 0.633 / 0.652 / 0.648 / 0.582 / 0.652 | 0.633±0.027 |
| `b095` | `n3-total` | 0, 0, 1, 1, 1 | 0.6±0.5 | 0.620 / 0.645 / 0.607 / 0.630 / 0.617 | 0.624±0.013 |
| `b095` | `n5-total` | 0, 0, 0, 1, 0 | 0.2±0.4 | 0.654 / 0.646 / 0.609 / 0.638 / 0.617 | 0.633±0.017 |

Aplicando la **regla de varianza pre-registrada** (`|media_A − media_B| > sd_A + sd_B`), contra
`b095 n1` como referencia:

| Comparación | Δ degeneradas | Dispersión sumada | Veredicto |
| --- | ---: | ---: | :---: |
| `b095 n1` → `n3-per-start` | +0.2 | 0.9 | **empate** |
| `b095 n1` → `n5-per-start` | +0.2 | 0.9 | **empate** |
| `b095 n1` → `n3-total` | 0.0 | 1.0 | **empate** |
| `b095 n1` → `n5-total` | −0.4 | 0.9 | **empate** |

Lo mismo para el balance mínimo: la mayor diferencia contra `n1` es −0.029 (`n3-per-start`),
contra una dispersión sumada de 0.041 → **empate**. Las cuatro comparaciones son empates.

**Los cuatro brazos de multi-arranque empatan con N=1 en las dos métricas de cola.** Bajar de 0.6
a 0.2 rutas degeneradas con `n5-total` es tentador de leer como mejora, pero es exactamente el
tipo de diferencia que la regla de varianza existe para rechazar: 1 ruta en 5 réplicas contra 3 en
5, con desviaciones de 0.4–0.5. No se reporta como mejora.

Además, **el multi-arranque no reduce la dispersión**, que era la vía por la que podría haber
matado la cola. Cruces en `reference-n1607`, réplica por réplica:

| Configuración | Arm | Cruces ordenados | media ± sd |
| --- | --- | --- | ---: |
| `b095` | `n1` | 17, 18, 21, 23, 26 | 21.0±3.3 |
| `b095` | `n3-per-start` | 17, 18, 25, 26, 32 | 23.6±5.5 |
| `b095` | `n5-per-start` | 17, 19, 19, 26, 29 | 22.0±4.6 |
| `b095` | `n3-total` | 27, 31, 31, 33, 44 | 33.2±5.7 |
| `b095` | `n5-total` | 38, 38, 39, 42, 51 | 41.6±4.9 |

Tomar el mínimo de N corridas **por objetivo del solver** no estrecha la distribución de una
métrica que el objetivo no contiene. Es el riesgo #2 declarado antes de medir, y se materializó.

### La respuesta explícita: ¿el presupuesto total fijo mata la cola?

**No.** Y la respuesta completa es peor que un empate:

1. **En la cola, empata** con N=1 (tabla anterior): 0.2±0.4 vs 0.6±0.5 rutas degeneradas,
   0.633±0.017 vs 0.645±0.015 de balance mínimo. Ninguna diferencia supera la dispersión.
2. **En la media, degrada de forma real.** Con el presupuesto repartido, cada arranque converge
   menos y ni siquiera el mejor de los cinco recupera lo perdido:

| Configuración | Arm | travel `n1607` | Δ vs `actual n1` | Veredicto | Cruces `n1607` | Δ vs `actual n1` |
| --- | --- | ---: | ---: | :---: | ---: | ---: |
| `actual` | `n1` | 61 433±943 | — | — | 71.4±7.2 | — |
| `actual` | `n3-total` | 66 538±526 | **+8.3 %** | **real** | 81.2±13.3 | +13.7 % (empate) |
| `actual` | `n5-total` | 67 177±415 | **+9.3 %** | **real** | 67.8±7.3 | −5.0 % (empate) |
| `b095` | `n1` | 62 088±1 738 | +1.1 % | empate | 21.0±3.3 | −70.6 % (real) |
| `b095` | `n3-total` | 63 484±1 474 | +3.3 % | empate | 33.2±5.7 | −53.5 % (real) |
| `b095` | `n5-total` | 64 973±925 | **+5.8 %** | **real** | 41.6±4.9 | −41.7 % (real) |

`b095 + n5-total` **falla el criterio de travel** (+5.8 % contra un techo de +3 %, y la diferencia
es real bajo la regla de varianza). Los cruces siguen pasando el −30 %, pero pierden la mitad de
su ventaja: de −70.6 % a −41.7 %.

**Conclusión para la conversación de adopción: el multi-arranque no sale gratis.** La lectura
esperanzada —"si (b) también mata la cola, es una mejora sin costo"— queda descartada por los
datos: (b) no mata la cola *y además* rompe un criterio que N=1 pasaba. El intercambio real no es
"5× cómputo por estabilidad", es "5× cómputo por nada medible", o "mismo cómputo por peor travel".

### Criterio completo — `feasible-floor-b095` con multi-arranque

Contra el control de producción `actual n1`. `n5-per-start` es el brazo más favorable posible al
multi-arranque (5× cómputo):

| Criterio | `b095 n1` | `b095 n5-per-start` | `b095 n5-total` |
| --- | --- | --- | --- |
| `n1607` cruces −≥30 % | −70.6 % (real) ✅ | −69.2 % (real) ✅ | −41.7 % (real) ✅ |
| `n1607` travel ≤+3 % | +1.1 % (empate) ✅ | −0.4 % (empate) ✅ | **+5.8 % (real) ❌** |
| `n1607` k ≤26 | 25.0±0.0 ✅ | 25.0±0.0 ✅ | 25.0±0.0 ✅ |
| Áreas `relleno_msf` −≥30 % | −40.2 / −96.2 / −83.0 % ✅ | −51.9 / −95.9 / −83.0 % ✅ | −49.1 / −95.9 / −83.0 % ✅ |
| Áreas cruces sin empeorar | mejoran las tres ✅ | mejoran las tres ✅ | mejoran las tres ✅ |
| Drops = 0 | 0 en 60 filas ✅ | 0 en 60 filas ✅ | 0 en 60 filas ✅ |
| Balance ≥0.60 en toda instancia | 0 <0.60 en media, **0 en peor réplica** ✅ | 0 en media, **1 en peor réplica** (`battery-sparse-n250` 0.582) ⚠️ | 0 en media, 0 en peor réplica ✅ |
| **0 rutas degeneradas** | **3 filas de 60** ❌ | **4 filas de 60** ❌ | **1 fila de 60** ❌ |

**Ningún brazo pasa el criterio completo.** El fallo es siempre el mismo y siempre en la misma
instancia: las 17 filas degeneradas de las 600 están **todas** en `reference-n1607`, y todas
tienen `dur_min` entre 6 759 s y 9 257 s —muy por encima del umbral de 1 800 s—, así que la marca
viene del **conteo de paradas**: rutas de casi dos horas con menos de 5 árboles censados. Es la
misma patología que el ciclo anterior encontró en 1 de 5 semillas, y el multi-arranque no la toca.

Un dato que conviene registrar: con los conjuntos de semillas de este ciclo, `b095 n1` degenera
en **3 de 5 réplicas**, no en 1 de 5 como midió el ciclo anterior. Las dos cifras son consistentes
entre sí dadas sus dispersiones (0.6±0.5 aquí), y juntas dicen algo más fuerte que cualquiera por
separado: la ruta degenerada de `b095` **no es un accidente raro de una semilla desafortunada**,
es un modo de fallo frecuente del brazo.

### Un hallazgo lateral: `actual` también tiene cola, y sólo aparece al repartir el presupuesto

El control de producción produjo **2 rutas degeneradas** (réplicas 1 y 2 de `actual n3-total`), su
único fallo en 300 filas. Con presupuesto completo `actual` nunca degenera. No supera la regla de
varianza (0.4±0.5 contra 0.0±0.0 → 0.4 < 0.5, **empate**), así que no se reporta como diferencia
real, pero deja la observación registrada: recortar el tiempo de convergencia es capaz de sacar a
producción de su régimen limpio.

### Por qué el multi-arranque no compró nada

La lectura más útil del ciclo es el mecanismo, y la da el travel de los brazos `per-start`:
`b095` pasa de 62 088±1 738 (N=1) a 61 209±1 167 (N=5), un **empate** bajo la regla de varianza.
Con `T = 120 s`, cinco arranques mejoran el objetivo del solver tan poco que ni siquiera se
distingue del ruido entre réplicas. La GLS ya está en su meseta cuando el arranque termina: el
multi-arranque está muestreando cinco veces casi el mismo punto.

Eso explica los dos resultados a la vez. Con presupuesto por arranque no hay ganancia porque no
hay dispersión que explotar; con presupuesto total sí hay dispersión —cada arranque converge
mucho menos— pero el mínimo de cinco soluciones malas sigue siendo peor que una buena.

### Veredicto y decisión de adopción

**Hipótesis falsada.** El multi-arranque no elimina la cola: 0 de 4 brazos alcanzan las
condiciones pre-registradas (0 rutas degeneradas y balance ≥0.60 en todas las réplicas), y las
cuatro comparaciones contra N=1 son **empates** bajo la regla de varianza. `feasible-floor-b095`
sigue fallando el mismo octavo criterio que fallaba antes, así que **sigue sin haber una ganadora
verificada en la serie**.

**No se cambia ningún default de producción.** El multi-arranque queda implementado pero opt-in
(`--starts`, `--budget` del driver; `--starts 1` recorre el mismo camino de código de siempre).
Recomendación explícita: **no adoptarlo**. Con presupuesto por arranque cuesta 5× el cómputo para
un empate; con presupuesto total cuesta un criterio roto.

**Lo que este ciclo cierra.** La observación que dejó abierta el ciclo anterior —"reducir la
varianza resolviendo con varias semillas y quedándose con la mejor"— ya no es una hipótesis sin
evidencia: está medida, con 600 filas y barras de error, y es negativa. La causa está
identificada y es estructural, no de sintonización: seleccionar por el objetivo del solver no
puede estrechar la distribución de una métrica que el objetivo no contiene, y a `T = 120 s` la
distribución de la que se muestrea ya es casi degenerada. Subir N no lo arregla; N=3 y N=5 dan lo
mismo.

**Hacia dónde apunta.** La degeneración de `b095` es de **conteo de paradas** en
`reference-n1607` —rutas de ~2 h con menos de 5 árboles— y sobrevivió a los cinco arms. No es
ruido de búsqueda: es una solución que el modelo considera buena. Atacarla requiere que el
**modelo** la penalice, no que se sortee más veces la misma búsqueda. Eso es consistente con el
cierre del ciclo anterior: la palanca está fuera de la varianza del solver.

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
`multistart-sweep-20260721-<cell>-<arm>.csv` (10 archivos × 60 filas), que es lo que se publica
junto a este reporte. Las 50 corridas se ejecutaron con 10 flujos en paralelo sobre la misma
máquina, así que `wall_clock_sec` no es comparable contra barridos previos (riesgo #4). Entre arms
sólo se usa para verificar la razón 1×/3×/5× de arranques, no como medida de rendimiento: la
contención de CPU es la misma en promedio, pero no fila a fila.
