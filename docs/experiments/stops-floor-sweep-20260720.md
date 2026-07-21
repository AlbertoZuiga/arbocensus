# Barrido de pisos anti-stub: piso de paradas vs piso de tiempo bajo

**Fecha:** 2026-07-20
**Datos:** `stops-floor-sweep-20260720.csv`.

> **Corrección posterior — `sweep-metrology-20260720.md`.** Las cifras de este reporte se
> midieron con un instrumento con dos defectos. (1) Las columnas `seed` **no eran réplicas**: el
> driver escribía la semilla en el CSV pero nunca la pasaba al solver, así que toda "media sobre
> 3 semillas" es la media de tres copias de una misma corrida y **ninguna cifra tiene barras de
> error**. (2) `relleno_sec` mide sobre un cero inalcanzable y sesgado por instancia: en
> `area-26-n157` contaba como relleno un 47.9 % de geometría irreducible. Las filas siguen siendo
> mediciones válidas de una corrida; los **veredictos de relleno** y las comparaciones de pocos
> puntos porcentuales entre brazos, no. El re-juicio de estas filas contra una cota alcanzable
> está en `sweep-metrology-20260720-rejudge.csv` (columna `relleno_msf_sec`).

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

288 filas (8 celdas × 12 instancias × 3 semillas). Medias sobre semillas. **Drops = 0 en las
288 filas**, en todas las celdas y todas las instancias. Como en el barrido anterior, los
criterios se evalúan sobre la media de las 3 semillas, no sobre el peor caso.

### n=1607 (denso saturado)

Control `actual`: k=25, cruces 88.0, travel 60 632 s, relleno 33 576 s, balance 0.833.

| Celda | k | cruces | Δ cruces | travel | Δ travel | relleno | balance | degeneradas | dur_min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no-floor` | 25 | 5.7 | −94 % | 52 146 | **−14.0 %** | −25.3 % | **0.011** | **1** | **120** |
| `no-floor-stops5` | 25 | 8.0 | −91 % | 58 286 | −3.9 % | −7.0 % | 0.727 | 0 | 7 835 |
| `no-floor-stops10` | 25 | 6.3 | −93 % | 58 344 | −3.8 % | −6.8 % | 0.727 | 0 | 7 835 |
| `no-floor-stops15` | 25 | **4.3** | **−95 %** | 59 034 | −2.6 % | −4.8 % | 0.647 | 0 | 6 969 |
| `no-floor-lowfloor3600` | 25 | 5.7 | −94 % | 58 264 | −3.9 % | −7.1 % | 0.718 | **1** | 7 736 |
| `no-floor-lowfloor5400` | 25 | 12.0 | −86 % | 60 164 | −0.8 % | −1.4 % | 0.791 | 0 | 8 505 |
| `feasible-floor-b095` | 25 | 6.0 | −93 % | 59 338 | −2.1 % | −3.9 % | 0.694 | 0 | 7 470 |

Las siete celdas cumplen los tres criterios de n=1607 (cruces −≥30 %, travel ≤+3 %, k ≤26).

### Balance y degeneración sobre toda la suite

| Celda | balance mínimo (instancia) | instancias bajo 0.60 | degeneradas (suite) | peor `dur_min` |
| --- | ---: | ---: | ---: | ---: |
| `actual` | 0.832 (battery-n200) | 0 | **0** | 7 182 |
| `feasible-floor-b095` | **0.652** (battery-n100) | **0** | **0** | 6 159 |
| `no-floor` | 0.011 (reference-n1607) | 4 | 2 | 120 |
| `no-floor-stops5` | 0.109 (battery-n200) | 3 | 1 | 1 168 |
| `no-floor-stops10` | 0.370 (battery-n800) | 3 | **0** | 3 970 |
| `no-floor-stops15` | 0.370 (battery-n800) | 2 | **0** | 3 970 |
| `no-floor-lowfloor3600` | 0.370 (battery-n800) | 2 | 1 | 3 970 |
| `no-floor-lowfloor5400` | 0.506 (battery-sparse-n250) | 3 | **0** | 5 448 |

### Áreas reales chicas — relleno

| Celda | area-26-n157 | area-27-n72 | area-29-n43 |
| --- | ---: | ---: | ---: |
| `no-floor` | −25.7 % | −81.9 % | −62.6 % |
| `no-floor-stops10` | −25.7 % | −81.9 % | −62.6 % |
| `no-floor-stops15` | −20.4 % | −81.9 % | −62.6 % |
| `no-floor-lowfloor5400` | −22.1 % | −81.9 % | −62.6 % |
| `feasible-floor-b095` | −20.8 % | −81.5 % | −62.6 % |

Los cruces no empeoran en ninguna área para ninguna celda (0 → 0 en las tres, salvo area-27
que baja de 6 a 0). **`area-26-n157` vuelve a ser la instancia que ninguna celda arregla:**
su relleno no baja del −26 % en ningún brazo, contra el −50 % exigido.

### Estado de cada criterio (a priori)

| Criterio | `stops5` | `stops10` | `stops15` | `lowfloor3600` | `lowfloor5400` | `b095` | `no-floor` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| n=1607 cruces −≥30 % | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| n=1607 travel ≤+3 % | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| n=1607 k ≤26 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Áreas: relleno −≥50 % | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Áreas: cruces sin empeorar | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Drops = 0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Balance ≥0.60 en toda instancia | ❌ | ❌ | ❌ | ❌ | ❌ | **✅** | ❌ |
| 0 rutas degeneradas | ❌ | **✅** | **✅** | ❌ | **✅** | **✅** | ❌ |

**Ninguna celda cumple el criterio completo**, por el mismo motivo que en el ciclo anterior: el
relleno de `area-26-n157`. `feasible-floor-b095` es de nuevo la única que falla **solo** ese
criterio.

### Lectura

- **El piso de paradas hace exactamente lo que prometía: mata los stubs sin pagar relleno.**
  `no-floor-stops10` y `no-floor-stops15` llevan la suite a **0 rutas degeneradas** —contra 2 de
  `no-floor`— conservando la geometría del brazo sin piso (cruces n=1607 6.3 y 4.3 vs 5.7) y
  gastando en relleno un −6.8 % / −4.8 % respecto del control. La ruta de un solo árbol de
  `no-floor` (120 s) desaparece: el peor `dur_min` sube de 120 s a 3 970 s.
- **La comparación honesta contra el piso de tiempo confirma el mecanismo.** A igual objetivo
  anti-stub, `no-floor-lowfloor5400` también llega a 0 degeneradas, pero lo compra devolviendo
  el relleno: en n=1607 su relleno baja apenas −1.4 % (contra −6.8 % de `stops10`), su travel
  −0.8 % (contra −3.8 %) y sus cruces son el doble (12.0 vs 6.3). Y el piso de tiempo más bajo,
  `lowfloor3600`, ni siquiera alcanza el objetivo: **deja una ruta degenerada en n=1607**. Es
  decir: el piso de tiempo o es demasiado bajo para prohibir stubs, o es lo bastante alto como
  para empezar a pagarse con relleno. El piso de paradas no tiene ese dilema.
- **`stops5` es demasiado flojo, y falla por la vía que predice la propia definición.** Con
  5 paradas de mínimo, en battery-n200 queda una ruta de 1 168 s: cumple el piso de paradas y
  aun así dura menos de media mañana. La degeneración la marca por **duración**, no por conteo.
  El piso de paradas prohíbe el stub de conteo; no prohíbe una ruta corta y compacta.
- **Pero el piso de paradas NO arregla el balance, y esa es su limitación central.**
  `stops10` y `stops15` siguen con balance mínimo 0.370 (battery-n800) y 2–3 instancias bajo
  0.60. Es coherente: una ruta puede cumplir 10 paradas y durar 66 minutos. **"Sin stubs" y
  "balanceado" son objetivos distintos**, y un piso de conteo solo compra el primero. El único
  brazo que compra los dos sigue siendo el piso factible, porque su piso es de duración y está
  escalado a lo que la instancia puede realmente sostener.
- **`feasible-floor-b095` queda confirmado en la columna que faltaba.** El barrido del 19 no
  pudo verificar su no-degeneración; medida de primera mano aquí, es **0 en las 12 instancias**,
  con `dur_min` peor de 6 159 s. Su candidatura reabierta se sostiene: pasa balance (min 0.652),
  degeneración (0), drops (0) y los tres criterios de n=1607 (cruces −93 %, travel −2.1 %,
  k=25), y falla únicamente el relleno de area-26 —que ningún brazo de esta serie logra.

### Head-to-head

| | `no-floor` | `no-floor-stops10` | `feasible-floor-b095` |
| --- | ---: | ---: | ---: |
| n=1607 cruces | 5.7 | 6.3 | 6.0 |
| n=1607 travel | −14.0 % | −3.8 % | −2.1 % |
| n=1607 relleno | −25.3 % | −6.8 % | −3.9 % |
| Balance mínimo suite | 0.011 | 0.370 | **0.652** |
| Instancias bajo 0.60 | 4 | 3 | **0** |
| Rutas degeneradas | 2 | **0** | **0** |
| Peor `dur_min` | 120 s | 3 970 s | **6 159 s** |

El orden es monótono y legible: `no-floor` compra geometría y travel al precio de rutas
inaceptables; el piso de paradas recupera la aceptabilidad mínima (0 degeneradas) devolviendo
dos tercios de la ganancia de travel; el piso factible recupera además el balance devolviendo
otro poco. **No hay celda que domine a las otras dos**: cada escalón compra un criterio con
travel y relleno.

### Grilla de span espacial sobre `no-floor-stops10`

Celda elegida para la grilla: **`no-floor-stops10`**. Entre las celdas con 0 degeneradas de la
familia nueva, `stops10` y `stops15` empatan en balance mínimo (0.370, battery-n800); el
desempate es n=1607, donde `stops10` tiene mejor balance (0.727 vs 0.647), mejor travel (−3.8 %
vs −2.6 %) y cruces igualmente muy por debajo del umbral (6.3 vs 4.3). `lowfloor5400` queda
fuera por su relleno (−1.4 % en n=1607).

El coeficiente 3 es la medición ya reportada arriba. 72 filas nuevas (2 coeficientes × 12
instancias × 3 semillas).

| n=1607 | coef 3 | coef 10 | coef 30 |
| --- | ---: | ---: | ---: |
| k | 25 | 25 | **26** |
| cruces | 6.3 | **3.0** | 18.0 |
| travel Δ vs `actual` | −3.8 % | **+6.3 %** | +0.9 % |
| relleno Δ | −6.8 % | **+11.4 %** | +1.7 % |
| balance | 0.727 | 0.859 | **0.011** |
| degeneradas | 0 | 0 | **1** |
| `dur_min` | 7 835 s | 9 244 s | **120 s** |

| suite | coef 3 | coef 10 | coef 30 |
| --- | ---: | ---: | ---: |
| balance mínimo | 0.370 | 0.385 | 0.011 |
| instancias bajo 0.60 | 3 | 2 | 4 |
| degeneradas | 0 | 0 | 1 |

**Ningún coeficiente mejora al 3.**

- **coef 10** compra geometría y balance con relleno: en n=1607 los cruces bajan a 3.0 y el
  balance sube a 0.859, pero el travel se va a **+6.3 %** (viola el tope de +3 %) y el relleno a
  **+11.4 %**, o sea por encima del control. Apretar el término espacial obliga a rutas
  compactas que rellenan tiempo dentro de su zona: es el mismo intercambio del span cost global
  del ciclo anterior, por otra puerta.
- **coef 30 se rompe, y de forma no monótona**: reaparece la ruta de un solo árbol (`dur_min`
  120 s, balance 0.011, 1 degenerada) y k sube a 26. Con el término espacial tan caro, aislar un
  árbol lejano en su propia ruta sale más barato que la penalidad de 10 000/parada del piso: el
  piso de paradas **no es infalible**, es un precio, y un término espacial suficientemente caro
  lo compra.
- La sospecha que justificaba la grilla —"el 3 se calibró con el soft lower dominante; sin ese
  piso la escala relativa cambió"— queda **refutada**: el 3 sigue siendo el mejor de los tres
  también sin piso de duración.

---

## Veredicto final

**Ninguna celda de la familia de pisos anti-stub queda verificada contra su criterio a priori
completo.** No se cambia ningún default de producción.

| Celda | Veredicto | Resumen |
| --- | --- | --- |
| `no-floor-stops5` | **No verificada** | Piso demasiado flojo: deja una ruta de 1 168 s en battery-n200 (degenerada por duración, no por conteo) y balance 0.109. |
| `no-floor-stops10` | **No verificada — balance** | Cumple lo que prometía: 0 degeneradas, cruces n=1607 −93 %, travel −3.8 %, relleno −6.8 %. Falla balance (mín. 0.370, 3 instancias bajo 0.60) y el relleno de area-26. |
| `no-floor-stops15` | **No verificada — balance** | Mejor geometría de la suite en n=1607 (cruces 4.3, −95 %) y 0 degeneradas, pero balance mín. 0.370 y balance 0.578 en area-26. |
| `no-floor-lowfloor3600` | **No verificada** | El piso de tiempo bajo no alcanza el objetivo anti-stub: 1 ruta degenerada en n=1607. |
| `no-floor-lowfloor5400` | **No verificada** | Sí mata los stubs (0 degeneradas) pero devolviendo el relleno: n=1607 relleno −1.4 %, travel −0.8 %, cruces 12.0 (el doble que `stops10`). Balance mín. 0.506. |
| `no-floor-stops10@span{10,30}` | **No verificada** | coef 10 viola travel (+6.3 %) y sube el relleno (+11.4 %); coef 30 reintroduce la ruta de un árbol. El coeficiente 3 no se recalibra. |
| `feasible-floor-b095` | **La más cercana, ahora verificada en degeneración** | Único brazo que pasa balance en las 12 instancias (mín. 0.652) **y** 0 rutas degeneradas medidas de primera mano. Falla solo el relleno de area-26 (−20.8 % contra −50 %). |

Síntesis:

- **La hipótesis del piso no paddeable se confirma en su mecanismo y se acota en su alcance.**
  Un piso de paradas prohíbe efectivamente los stubs sin comprar relleno, y la comparación
  contra pisos de tiempo bajos lo demuestra en la dirección esperada: a igual efecto anti-stub,
  el piso de tiempo cuesta relleno y cruces (`lowfloor5400`), y si se baja lo suficiente para
  no costarlos, deja de prohibir stubs (`lowfloor3600`).
- **Pero el problema que quedaba abierto no era solo el stub: era el balance.** El piso de
  paradas resuelve el primero y no toca el segundo, porque diez paradas juntas pueden durar una
  hora. Ese es el hallazgo negativo útil del ciclo: **conteo de paradas y duración no son
  intercambiables como criterio de aceptabilidad de una ruta**, y el criterio operativo que
  importa (una ruta que llene la jornada de un censista) es de duración.
- **Un piso de duración escalado a la instancia sigue siendo la única vía que compra ambos.**
  `feasible-floor-b095` cierra este ciclo confirmado en la columna que le faltaba, y su único
  fallo pendiente —el relleno de `area-26-n157`— es el mismo que ningún brazo de esta serie
  (piso factible, sin piso, span global, piso de paradas, piso de tiempo bajo, grilla espacial)
  ha logrado mover. **`area-26-n157` es el problema abierto, no el piso.**
- Una idea derivada, no probada aquí y anotada como tal: un piso **combinado** —conteo de
  paradas como cota dura anti-stub y piso de duración escalado como término de balance— es la
  composición natural de los dos resultados, pero no se midió en este barrido y no se puede
  afirmar nada sobre ella.

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
      --only-cell no-floor-stops10 --spatial-span-coef "$coef"
done
```

Las celdas se corrieron repartidas en tres flujos paralelos, cada uno escribiendo su propio CSV
parcial (el driver es resumible por celda, no por fila concurrente), y los parciales se
concatenaron en el CSV final. La secuencia de arriba, en serie sobre un único CSV, produce el
mismo resultado.
