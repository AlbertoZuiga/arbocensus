# Diagnóstico de `area-26-n157` y barrido del piso combinado (duración escalada + paradas)

**Fecha:** 2026-07-20
**Datos:** `combined-floor-sweep-20260720.csv` (barrido),
`combined-floor-diagnostic-20260720.csv` (diagnóstico) y
`combined-floor-decomposition-20260720.csv` (aritmética estructural).

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual, coeficiente
de span espacial 3) intactos. Los brazos nuevos son opt-in.

Este reporte cierra el ciclo abierto por `stops-floor-sweep-20260720.md`, cuyo veredicto fue:
el piso de paradas mata las rutas stub sin comprar relleno (mecanismo confirmado) pero no da
balance, porque diez paradas juntas pueden durar una hora; `feasible-floor-b095` sigue siendo
el único brazo que compra balance y no-degeneración a la vez, y falla **solo** el relleno de
`area-26-n157`. Ese reporte dejó anotadas dos cosas sin medir, y las dos se miden acá:

1. `area-26-n157` es la instancia que ningún brazo arregla —tres ciclos consecutivos fallaron
   el mismo criterio en la misma instancia—, y nunca se verificó si el criterio es
   **alcanzable** en ella.
2. Un piso **combinado** (conteo de paradas como cota anti-stub + piso de duración escalado
   como término de balance) es la composición natural de los dos resultados, y no se midió.

El orden importa: **el diagnóstico se corre y se resuelve primero**, porque si el criterio de
relleno de `area-26-n157` resulta inalcanzable, seguir agregando brazos de piso es correr
contra un objetivo imposible.

---

## Parte A — Diagnóstico de `area-26-n157`

### Hipótesis a falsar

El relleno de `area-26-n157` es **estructural**, no un artefacto del piso: la instancia
resuelve con un k̂ de más, de modo que k̂·(cualquier piso) excede el trabajo disponible, y
ninguna penalización puede crear trabajo que no existe. Si es así, la palanca no es el piso
sino **k**, y los ciclos anteriores vinieron fallando contra un objetivo inalcanzable.

Motivación cuantitativa, leída del CSV del ciclo anterior
(`stops-floor-sweep-20260720.csv`, medias de 3 semillas sobre `area-26-n157`):

| Celda | k | travel | relleno |
| --- | ---: | ---: | ---: |
| `actual` | 3.0 | 4 962 | 2 579 |
| `no-floor` | 3.0 | 4 300 | 1 917 |
| `feasible-floor-b095` | 3.0 | 4 425 | 2 042 |

**k = 3.0 en las diez celdas medidas del ciclo anterior, sin excepción.** Ningún brazo movió
k jamás. Y `no-floor` —sin ningún piso de duración, es decir, con el mecanismo causal del
relleno completamente apagado— deja el 74 % del relleno del control. Eso ya sugiere que el
residuo no es padding inducido por el piso, sino otra cosa; el diagnóstico lo decide con
aritmética en vez de con sospecha.

### Definiciones y cotas (fijadas antes de medir)

Notación: `n` nodos, `k` rutas abiertas, servicio `s = 120 s/árbol`, `T_max = 10 800 s`,
`nn̄` = media de la distancia al vecino más cercano (la misma que usa el driver).

El driver define **relleno** como el exceso de travel sobre una cota inferior de vecino más
cercano:

```
relleno := travel_total − (n − k) · nn̄
```

Sobre esa definición se fijan tres cotas, todas verificables:

- **(LB-geom) Cota geométrica.** Un conjunto de `k` caminos abiertos que cubre los `n` nodos
  es un bosque generador de `n − k` aristas y `k` componentes. Por lo tanto
  `travel_total ≥ MSF_k`, el bosque generador mínimo de `k` componentes (= MST menos las
  `k − 1` aristas más pesadas). Se calcula sobre la matriz simetrizada `min(d_ij, d_ji)`, lo
  que sólo puede subestimar el costo dirigido: la cota sigue siendo válida.
- **(LB-piso) Cota inducida por el piso.** Si toda ruta termina en `≥ F`, entonces
  `travel_total ≥ k · F − n · s`.
- **(UB-tmax) Techo de factibilidad.** Toda ruta cumple `≤ T_max`, así que
  `travel_total ≤ k · T_max − n · s`. Si el techo es menor que `MSF_k`, ese `k` es
  **infactible** y el solver no puede elegirlo.

De donde, para cada `k`, la cota inferior de relleno que ese `k` impone:

```
relleno_LB(k, F) = max(LB-geom, LB-piso) − (n − k) · nn̄
```

### Mediciones

1. **Descomposición** de `area-26-n157`: `n`, servicio total, `nn̄`, `MSF_k` para
   `k ∈ {1, 2, 3, 4}`, saturación a priori `n·s / (k·T_max)`, techo `UB-tmax` por `k`, y
   `relleno_LB(k, F)` para el piso de producción y para piso nulo.
2. **Frontera relleno-vs-balance:** grilla `beta ∈ {0.50, 0.60, 0.70, 0.85, 0.95}` del piso
   factible, **sólo en esta instancia** (hoy sólo existen `b085`/`b090`/`b095`; se agregan los
   beta bajos). Pregunta: ¿existe algún beta con relleno **−≥50 %** *y* balance **≥0.60**?
3. **Palanca nunca probada acá — k forzado.** Resolver con exactamente `k_observado − 1 = 2`
   vehículos, sin buffer. Si el relleno desaparece con `k−1`, queda probado que era exceso de
   vehículos; si resulta infactible o produce drops, queda probado que `k = 3` es forzado por
   `T_max` y que el relleno con `k = 3` es un piso estructural.

### Regla de reescritura del criterio (fijada antes de medir)

Una **imposibilidad medida** es un resultado válido, no un fracaso. Si y sólo si el
diagnóstico demuestra que `relleno_LB(k, F) > 0.5 · relleno_actual` para todo `k` factible,
el criterio de relleno de `area-26-n157` se reescribe **contra esa cota medida**, se deja
registrada la aritmética que lo respalda y el cambio se commitea **antes de correr el barrido
de la Parte B**. Fuera de ese caso el criterio heredado no se toca. En ningún caso se
renegocia un criterio después de mirar resultados del barrido.

---

## Parte B — Barrido del piso combinado

### Hipótesis

Un piso de **duración escalado a la instancia** es lo que compra balance (es el único
mecanismo que lo logró en toda la serie). Un piso de **paradas** es lo que prohíbe rutas stub
sin comprar relleno (mecanismo ya confirmado). Hoy son mutuamente excluyentes en el código:
cada uno se activa por el prefijo del nombre del brazo. **Compuestos**, un beta **bajo**
(0.60–0.70, nunca probado: la grilla existente sólo llega a 0.85) dejaría el piso de duración
holgado —y por lo tanto sin relleno—, mientras el piso de paradas impediría los stubs que ese
beta bajo habilitaría. Sería el primer brazo que compra los dos criterios que ningún brazo
simple compra junto.

### Brazos

Estrategia `spatial_term`, 3 semillas, suite completa de 12 instancias.

| # | Brazo | Mecanismo |
| --- | --- | --- |
| 1 | `feasible-floor-b{060,070,085}-stops10` | Piso de duración escalado `T_min_eff = min(T_min, β·trabajo_total/k_est)` **más** dimensión unitaria `Stops` con cota blanda inferior de 10 paradas por ruta activa, penalidad 10 000 por parada faltante. |

Controles, todos ya medidos en `stops-floor-sweep-20260720.csv` y releídos de ahí (cero
cómputo): `actual`, `feasible-floor-b095`, `no-floor-stops10`.

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s (2 min) |
| T_max | 10 800 s (3 h) |
| T_min | 7 200 s (2 h, default de producción) |
| Límite de tiempo del solver | heurístico `min(30 + 1.5·n, 120)` s |
| Semillas | 3 por celda |

### Instancias

Batería `{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales
`{157, 72, 43}` y `n=1607`. Cargadas con `load_instances` (UUID estables, cache OSRM acierta).

---

## Criterio de éxito a priori (heredado — no renegociable a posteriori)

Idéntico al del ciclo anterior, salvo la eventual reescritura del relleno de `area-26-n157`
que habilita la regla de la Parte A:

- **n=1607 (denso saturado):** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** relleno (`relleno_sec`) **−≥50 %** vs `actual`, cruces **sin
  empeorar**.
- **Global:** **0 drops**, **balance min/max ≥0.60** en toda instancia, y **0 rutas
  degeneradas**.
- **Ruta degenerada — definición ABSOLUTA:** menos de **5 paradas** O duración menor a
  **1 800 s**. Ambos umbrales absolutos, idénticos a los del ciclo anterior, de modo que la
  columna `degenerate_routes` es comparable con `stops-floor-sweep-20260720.csv`.
- σ(T) y balance se reportan en todas las celdas aunque el balance no sea criterio duro más
  allá del piso de cordura 0.60.
- **Head-to-head final** de la mejor celda contra `feasible-floor-b095`, `no-floor-stops10` y
  `actual`.

Los criterios se evalúan sobre la media de las 3 semillas, no sobre el peor caso.

### Nota de ejecución

Las celdas se corren en flujos paralelos sobre la misma máquina. El límite de tiempo del
solver es de reloj, así que la contención de CPU reduce iteraciones de GLS. Las columnas
`wall_clock_sec` y `t_metaheuristic_sec` no son comparables con las de barridos previos; los
controles releídos del CSV anterior se corrieron bajo el mismo esquema.

---

## Resultados — Parte A (diagnóstico de `area-26-n157`)

Datos: `combined-floor-decomposition-20260720.csv` (aritmética) y
`combined-floor-diagnostic-20260720.csv` (30 filas: 10 celdas × 3 semillas).

Los dos controles reproducen **exactamente** el ciclo anterior (`actual`: k=3, travel 4 962,
relleno 2 579; `no-floor`: k=3, travel 4 300, relleno 1 917), así que el arnés es comparable
fila a fila con `stops-floor-sweep-20260720.csv`.

### A.0 — Hallazgo metodológico: las tres semillas no son réplicas

El driver escribe `seed` al CSV y lo usa en la clave de reanudación, pero **nunca lo pasa al
solver** ni a los parámetros de búsqueda. Medido: en las **10 celdas** del diagnóstico, las 3
semillas dan **un único resultado distinto** (k, travel, relleno, balance, cruces y drops
idénticos, 30 filas).

Consecuencia, que alcanza también a los cuatro barridos previos de la serie: toda "media sobre
3 semillas" publicada es la media de tres copias del mismo número. **No hay ninguna estimación
de varianza en la serie**, y cada barrido costó 3× el cómputo necesario. Ninguna cifra previa
queda invalidada —las medias son correctas, sólo que de un único punto—, pero las diferencias
de pocos puntos porcentuales entre brazos nunca tuvieron barras de error que las respalden.

### A.1 — Descomposición: k=3 es el mínimo factible, no un exceso

`n = 157`, servicio total `18 840 s`, `nn̄ = 15.47 s`, `T_max = 10 800 s`.

| k | MSF_k (LB-geom) | LB-piso (T_min) | techo UB-tmax | ¿factible? | saturación a priori | relleno_LB (piso nulo) |
| ---: | ---: | ---: | ---: | :---: | ---: | ---: |
| 1 | 4 256 | 0 | **−8 040** | **No** | 1.744 | — |
| 2 | 3 881 | 0 | **2 760** | **No** | 0.872 | — |
| **3** | **3 618** | **2 760** | 13 560 | **Sí** | 0.581 | **1 235** |
| 4 | 3 406 | 9 960 | 24 360 | Sí | 0.436 | 1 039 (7 592 con T_min) |

Dos lecturas, ambas aritméticas:

- **La hipótesis del "k̂ de más" queda REFUTADA.** `k = 3` es el **mínimo factible**, no un
  exceso. `k = 1` no alcanza ni para el servicio (el techo es negativo). `k = 2` es imposible
  con cobertura completa: la cota geométrica (3 881 s) supera todo el presupuesto de travel que
  `T_max` deja libre después del servicio (2 760 s). El solver no elige 3 por holgazanería:
  no puede elegir menos.
- **El piso de duración está FLOJO en el k que el solver elige.** Con `k = 3`, el T_min de
  producción obliga `travel ≥ 3·7 200 − 18 840 = 2 760 s`, pero la geometría ya obliga
  `≥ 3 618 s`. El piso **nunca es la restricción activa**. Por eso los tres ciclos anteriores
  devolvieron siempre k=3 y un relleno en una banda estrecha: estaban ajustando una restricción
  inactiva. (En `k = 4` el piso sí mordería, y con fuerza: `relleno_LB` salta a 7 592.)

### A.2 — Frontera beta: plana y no monótona

Grilla completa del piso factible sobre `area-26-n157` (relleno objetivo: **≤ 1 289 s**).

| Celda | T_min_eff | k | travel | relleno | Δ vs `actual` | balance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no-floor` (límite de piso nulo) | — | 3 | 4 300 | **1 917** | **−25.7 %** | 0.795 |
| `feasible-floor-b085` | escalado | 3 | 4 355 | 1 972 | −23.5 % | 0.754 |
| `feasible-floor-b070` | escalado | 3 | 4 374 | 1 991 | −22.8 % | 0.832 |
| `feasible-floor-b050` | escalado | 3 | 4 392 | 2 009 | −22.1 % | 0.834 |
| `feasible-floor-b095` | escalado | 3 | 4 425 | 2 042 | −20.8 % | 0.838 |
| `feasible-floor-b090` | escalado | 3 | 4 520 | 2 137 | −17.1 % | 0.821 |
| `actual` (T_min 7 200 completo) | 7 200 | 3 | 4 962 | 2 579 | — | 0.877 |

La respuesta a la pregunta pre-registrada —¿existe algún beta con relleno −≥50 % **y** balance
≥0.60?— es **no**. Y el patrón importa más que el número:

- Bajar el piso de β=0.95 a β=0.50 —recortarlo casi a la mitad— mueve el relleno de 2 042 a
  2 009: **1.6 %**. La grilla es **no monótona** (b090 es la peor, b085 la mejor de las seis;
  rango 1 972–2 137). Eso no es un mecanismo, es ruido de búsqueda.
- El único escalón real es `actual` (2 579) contra **cualquier** piso escalado (~2 000), y ahí
  satura. Es exactamente lo que predice A.1: una vez que el piso baja por debajo de lo que la
  geometría ya obliga, seguir bajándolo no compra nada.
- **El balance nunca fue la restricción activa acá**: ≥0.754 en toda la grilla, contra un
  umbral de 0.60.

### A.3 — La palanca k: alcanza el objetivo sólo abandonando árboles

| Corrida | k | drops | travel | relleno | Δ vs `actual` | balance | dur_min | dur_max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `actual`, k libre (estimador +5) | 3 | 0 | 4 962 | 2 579 | — | 0.877 | 7 294 | 8 321 |
| `actual`, k forzado a 3 (sin buffer) | 3 | 0 | 4 837 | 2 454 | −4.8 % | 0.896 | 7 517 | 8 391 |
| `actual`, **k forzado a 2** | 2 | **11** | 3 673 | **1 274** | **−50.6 %** | 0.978 | 10 478 | 10 715 |

- **El buffer de +5 vehículos tampoco es la causa:** forzar exactamente k=3 mejora el relleno
  un 4.8 %, lejos del 50 % pedido.
- **`k = 2` sí alcanza el criterio de relleno (−50.6 %) — dejando 11 árboles sin visitar.** Las
  dos rutas quedan clavadas contra `T_max` (10 478 y 10 715 s, techo 10 800). Es la
  confirmación empírica de A.1: con cobertura completa `k = 2` es infactible, y el solver sólo
  la vuelve factible descartando el 7 % del área. La aritmética cierra: con 146 árboles
  servidos el techo sube a `21 600 − 17 520 = 4 080 s`, y el travel observado (3 673) cae
  debajo.

**El criterio de relleno se alcanza únicamente no haciendo el trabajo.**

### A.4 — Veredicto del diagnóstico y decisión sobre el criterio

Qué quedó demostrado sobre `area-26-n157`:

1. `k = 3` es el **mínimo factible** con cobertura completa; la hipótesis del exceso de
   vehículos está **refutada**.
2. Con `k = 3`, el piso de duración **está flojo**: la geometría obliga más travel que
   cualquier piso de la familia. Ningún brazo de piso puede mover el relleno de esta instancia,
   y eso explica por qué tres ciclos fallaron el mismo criterio en la misma instancia.
3. La familia de pisos está **agotada**: desde piso nulo hasta T_min completo, el relleno vive
   en 1 917–2 579. El mejor valor posible (−25.7 %) es la mitad de lo que el criterio pide.
4. El criterio de relleno (−≥50 %) y el criterio de cero drops son **mutuamente insatisfacibles
   en esta instancia**: el único régimen que alcanza el primero (k=2) viola el segundo.

**Decisión sobre el criterio: NO se reescribe.** La regla pre-registrada exigía
`relleno_LB(k,F) > 0.5 · relleno_actual` para **todo** k factible. Con `k = 3` la cota medida es
`relleno_LB = 1 235` contra un objetivo de `1 289`: la cota **no supera** el objetivo, por 4 %.
La regla **no se dispara**, y el criterio heredado se mantiene intacto para la Parte B.

Lo que sí se puede afirmar es más débil que una imposibilidad formal, y se afirma en esos
términos: el objetivo exige `travel ≤ 3 673 s`, apenas **1.5 % por encima** de una relajación
de bosque generador que ignora la restricción de grado 2 de un camino y por lo tanto se sabe
**floja**, mientras que el mejor brazo medido está **18.9 %** por encima de ella. El criterio es
**empíricamente inalcanzable con la familia de pisos agotada**, no *demostrablemente*
imposible. `area-26-n157` seguirá contando como fallo en la Parte B; la diferencia es que ahora
el fallo está **explicado** y no es un misterio abierto.

Corolario para el diseño: el relleno residual de `area-26-n157` no es *padding* inducido por el
objetivo, es **geometría de ruteo irreducible** más una métrica cuyo punto cero
—`(n − k) · nn̄`— es una cota que ningún recorrido real puede tocar. La palanca, si alguna
queda, no está en el objetivo del VRP.

---

## Resultados — Parte B (barrido del piso combinado)

Datos: `combined-floor-sweep-20260720.csv`. Controles (`actual`, `no-floor-stops10`,
`feasible-floor-b095`) releídos de `stops-floor-sweep-20260720.csv`, cero cómputo.
**Drops = 0 y rutas degeneradas = 0 en las tres celdas nuevas, en las 12 instancias.**

Sobre las semillas: la celda `feasible-floor-b060-stops10` se corrió con las 3 semillas
pre-registradas para verificar en el código nuevo lo que A.0 midió en los brazos existentes.
Resultado: **12 de 12 instancias con un único resultado distinto** entre las 3 semillas. Con la
redundancia confirmada también en la ruta de código combinada, las otras dos celdas se
corrieron con una semilla. La desviación respecto del pre-registro es una economía de cómputo
demostrablemente sin efecto sobre las cifras: las semillas 2 y 3 son copias bit a bit de la 1.

### n=1607 (denso saturado)

Control `actual`: k=25, cruces 88.0, travel 60 632 s, relleno 33 576 s, balance 0.833.

| Celda | k | cruces | Δ cruces | travel | Δ travel | Δ relleno | balance | degeneradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no-floor-stops10` | 25 | 6.3 | −92.8 % | 58 344 | −3.8 % | −6.8 % | 0.727 | 0 |
| `feasible-floor-b095` | 25 | **6.0** | **−93.2 %** | 59 338 | −2.1 % | −3.9 % | 0.694 | 0 |
| `feasible-floor-b060-stops10` | 25 | 7.0 | −92.0 % | **58 159** | **−4.1 %** | **−7.4 %** | 0.727 | 0 |
| `feasible-floor-b070-stops10` | 25 | 8.0 | −90.9 % | 59 174 | −2.4 % | −4.3 % | 0.716 | 0 |
| `feasible-floor-b085-stops10` | 25 | 12.0 | −86.4 % | 60 209 | −0.7 % | −1.3 % | 0.791 | 0 |

Las tres celdas nuevas cumplen los tres criterios de n=1607 (cruces −≥30 %, travel ≤+3 %,
k ≤26).

### Balance por instancia (criterio: ≥0.60 en toda instancia)

| Instancia | `actual` | `stops10` | `b095` | `b060+s10` | `b070+s10` | `b085+s10` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 0.998 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| battery-n100 | 0.946 | 0.654 | **0.652** | 0.654 | 0.652 | 0.660 |
| battery-n200 | 0.832 | 0.590 | 0.679 | 0.667 | 0.629 | **0.597** |
| battery-n400 | 0.987 | 0.820 | 0.878 | 0.822 | 0.815 | 0.820 |
| battery-n800 | 0.852 | **0.370** | 0.749 | **0.454** | **0.463** | 0.749 |
| battery-n1000 | 0.837 | 0.479 | 0.688 | 0.727 | 0.743 | 0.948 |
| battery-sparse-n250 | 0.946 | 0.681 | 0.768 | 0.681 | 0.681 | 0.639 |
| battery-sparse-n500 | 0.847 | 0.875 | 0.812 | 0.875 | 0.812 | 0.812 |
| area-26-n157 | 0.877 | 0.795 | 0.838 | 0.832 | 0.832 | 0.754 |
| area-27-n72 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| area-29-n43 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| reference-n1607 | 0.833 | 0.727 | 0.694 | 0.727 | 0.716 | 0.791 |
| **mínimo** | 0.832 | 0.370 | **0.652** | 0.454 | 0.463 | 0.597 |
| **instancias <0.60** | 0 | 3 | **0** | 1 | 1 | 1 |

`feasible-floor-b085-stops10` falla el criterio de balance **por 0.003** (0.597 contra 0.600,
en battery-n200). Es un fallo, y como tal se registra: el criterio se fijó antes de correr.

### Áreas reales — relleno

| Celda | area-26-n157 | area-27-n72 | area-29-n43 |
| --- | ---: | ---: | ---: |
| `no-floor-stops10` | −25.7 % | −81.9 % | −62.6 % |
| `feasible-floor-b095` | −20.8 % | −81.5 % | −62.6 % |
| `feasible-floor-b060-stops10` | −21.1 % | −81.9 % | −62.6 % |
| `feasible-floor-b070-stops10` | −22.8 % | −81.9 % | −62.6 % |
| `feasible-floor-b085-stops10` | −23.5 % | −81.5 % | −62.6 % |

`area-27` y `area-29` superan el −50 % con holgura en todas las celdas; los cruces no empeoran
en ninguna área. **`area-26-n157` vuelve a fallar en las tres celdas nuevas** —y ahora, por la
Parte A, se sabe **por qué**: con k=3 forzado por `T_max`, el piso está flojo y el relleno
restante es geometría irreducible. Ningún brazo de piso podía moverlo.

### Estado de cada criterio (a priori)

| Criterio | `b060+s10` | `b070+s10` | `b085+s10` |
| --- | --- | --- | --- |
| n=1607 cruces −≥30 % | ✅ | ✅ | ✅ |
| n=1607 travel ≤+3 % | ✅ | ✅ | ✅ |
| n=1607 k ≤26 | ✅ | ✅ | ✅ |
| Áreas: relleno −≥50 % | ❌ (area-26) | ❌ (area-26) | ❌ (area-26) |
| Áreas: cruces sin empeorar | ✅ | ✅ | ✅ |
| Drops = 0 | ✅ | ✅ | ✅ |
| Balance ≥0.60 en toda instancia | ❌ (0.454) | ❌ (0.463) | ❌ (0.597) |
| 0 rutas degeneradas | ✅ | ✅ | ✅ |

**Ninguna celda cumple el criterio completo.**

### Head-to-head

| | `actual` | `no-floor-stops10` | `b095` | `b060+s10` | `b085+s10` |
| --- | ---: | ---: | ---: | ---: | ---: |
| n=1607 cruces | 88.0 | 6.3 | **6.0** | 7.0 | 12.0 |
| n=1607 travel | — | −3.8 % | −2.1 % | **−4.1 %** | −0.7 % |
| n=1607 relleno | — | −6.8 % | −3.9 % | **−7.4 %** | −1.3 % |
| Balance mínimo suite | **0.832** | 0.370 | **0.652** | 0.454 | 0.597 |
| Instancias <0.60 | **0** | 3 | **0** | 1 | 1 |
| Rutas degeneradas | **0** | **0** | **0** | **0** | **0** |

### Lectura

- **La composición funciona como mecanismo, y traza una frontera limpia.** Subir beta de 0.60 a
  0.85 mueve el balance mínimo 0.454 → 0.463 → 0.597 y degrada la geometría de forma monótona
  (cruces −92.0 % → −90.9 % → −86.4 %; travel −4.1 % → −2.4 % → −0.7 %). El piso de duración
  compra balance y cuesta geometría, exactamente como predecía la hipótesis.
- **Pero la premisa de la hipótesis era falsa.** El argumento para componer era: el piso de
  paradas mata los stubs, lo que *libera* un beta bajo para no comprar relleno. Sólo que
  `feasible-floor-b095` **ya tenía 0 rutas degeneradas** (medido en el ciclo anterior). No
  quedaba ningún stub que el piso de paradas pudiera prevenir. El componente anti-stub es
  **redundante** sobre un piso de duración ya escalado, y el beta bajo que supuestamente
  habilitaba sólo cuesta balance.
- **`feasible-floor-b085-stops10` está estrictamente dominado por `feasible-floor-b095`**, que
  es mejor en las cuatro dimensiones a la vez: balance (0.652 vs 0.597), cruces (−93.2 % vs
  −86.4 %), travel (−2.1 % vs −0.7 %) y relleno (−3.9 % vs −1.3 %). Añadir el piso de paradas
  no mejora nada y empeora todo.
- **`b060+s10` y `b070+s10` no están dominados, pero fallan el piso de cordura de balance.**
  Ofrecen el mejor travel y el mejor relleno de toda la serie en n=1607 (−4.1 % y −7.4 %) a
  cambio de un balance de 0.454–0.463 en battery-n800. Son puntos válidos de la frontera
  geometría-vs-balance, no configuraciones aceptables bajo el criterio vigente.
- **El cuello de botella de balance se movió de instancia.** En `no-floor-stops10` era
  battery-n800 (0.370); con beta 0.85 esa instancia se recupera a 0.749 y el mínimo pasa a
  battery-n200 (0.597). El piso escalado arregla la fragmentación del caso denso y deja
  expuesto un caso mediano distinto.

---

## Veredicto final

**Ninguna celda del piso combinado queda verificada contra su criterio a priori completo.** No
se cambia ningún default de producción.

| Celda | Veredicto | Resumen |
| --- | --- | --- |
| `feasible-floor-b060-stops10` | **No verificada — balance** | Mejor travel y relleno de la serie en n=1607 (−4.1 %, −7.4 %), 0 degeneradas, 0 drops. Balance mín. 0.454 (battery-n800). |
| `feasible-floor-b070-stops10` | **No verificada — balance** | Punto intermedio sin virtud propia: balance mín. 0.463, geometría peor que b060. |
| `feasible-floor-b085-stops10` | **No verificada — dominada** | Falla balance por 0.003 (0.597 vs 0.600, battery-n200) y además está **estrictamente dominada** por `feasible-floor-b095` en balance, cruces, travel y relleno. |

Síntesis:

- **La hipótesis del piso combinado queda refutada, y por una razón precisa: componía un
  mecanismo con otro que ya no tenía trabajo que hacer.** El piso de paradas resuelve los stubs
  que aparecen *sin* piso de duración; un piso de duración escalado no produce stubs (b095: 0
  degeneradas). Componerlos no suma, resta: obliga a bajar beta para dejar espacio, y el beta
  bajo cuesta balance sin comprar el relleno que se buscaba.
- **`feasible-floor-b095` sigue siendo el mejor candidato de toda la serie**, ahora por quinto
  ciclo consecutivo y por primera vez con un competidor directo que lo confirma por dominancia
  estricta. Pasa balance en las 12 instancias (mín. 0.652), 0 degeneradas, 0 drops y los tres
  criterios de n=1607.
- **El único criterio que le falta —el relleno de `area-26-n157`— quedó explicado y cerrado en
  la Parte A: no es alcanzable modificando el objetivo.** Con `k = 3` impuesto por `T_max`, el
  piso está flojo y el residuo es geometría de ruteo, no *padding*. **La familia de pisos está
  agotada como línea de investigación.**
- **Dos hallazgos transversales que valen más que los brazos medidos:**
  1. Las "3 semillas" de esta serie nunca fueron réplicas (A.0): el driver no las pasa al
     solver. Ninguna cifra publicada es incorrecta, pero ninguna tiene barras de error, y cada
     barrido costó 3× el cómputo necesario.
  2. La métrica `relleno` tiene su cero en `(n − k) · nn̄`, la suma de las distancias al vecino
     más cercano de cada nodo — una cota que **ningún recorrido real puede alcanzar**, porque
     viola la restricción de grado 2 de un camino. En `area-26-n157` el objetivo del criterio
     quedaba 1.5 % por encima de una relajación floja mientras el mejor brazo estaba 18.9 %
     por encima. La métrica mide geometría irreducible como si fuera relleno, en toda la serie.

Siguiente dirección, si la hay: no otro brazo de piso. O bien recalibrar la métrica de relleno
contra una cota alcanzable (por ejemplo el propio MSF_k, ya calculado por
`instance_decomposition`), o bien mover la palanca fuera del objetivo del VRP —`T_max`, el
tiempo de servicio o la partición territorial previa—, que es lo único que puede cambiar el k
que la aritmética impone.

---

## Reproducción

```bash
# Descomposición estructural (aritmética, sin solver)
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py instance_decomposition \
    --csv docs/experiments/combined-floor-decomposition-20260720.csv \
    --instance area-26-n157 --k-max 6 --floor 0 7200

# Diagnóstico de area-26: frontera beta + flota forzada
for cell in actual no-floor feasible-floor-b050 feasible-floor-b060 \
            feasible-floor-b070 feasible-floor-b085 feasible-floor-b090 \
            feasible-floor-b095; do
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv docs/experiments/combined-floor-diagnostic-20260720.csv \
      --only-instance area-26-n157 --only-cell "$cell"
done
for kv in 2 3; do
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv docs/experiments/combined-floor-diagnostic-20260720.csv \
      --only-instance area-26-n157 --only-cell actual --max-vehicles "$kv"
done

# Barrido del piso combinado
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py config_algorithm_sweep \
    --csv docs/experiments/combined-floor-sweep-20260720.csv \
    --only-cell feasible-floor-b060-stops10 --seeds 1 2 3
for cell in feasible-floor-b070-stops10 feasible-floor-b085-stops10; do
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv docs/experiments/combined-floor-sweep-20260720.csv \
      --only-cell "$cell" --seeds 1
done
```
