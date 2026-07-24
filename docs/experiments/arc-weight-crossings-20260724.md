# Peso lineal del arco contra los auto-cruces reales de calle

**Fecha:** 2026-07-24
**Estado al commitear esta sección:** pre-registro. Motivación, diseño, celdas, instancias,
métricas, predicciones y criterio se commitean **antes** de medir nada. Los resultados se
agregan después, sin tocar el criterio.

Todo corre por celdas del driver `config_algorithm_sweep`. La configuración de producción del
solver no cambia: el coeficiente nuevo tiene default `1`, que es el comportamiento actual bit a
bit. Lo nuevo es opt-in.

---

## 1. Motivación

El objetivo del VRP cobra **1 por segundo de arco**, contra 10 000/s del piso blando de duración
y 500/s del techo blando (`.claude/rules/ortools-vrp.md`, "Marginal price, not nominal weight").
En la instancia de referencia el travel es ~0,36 % del objetivo: el canal del arco prácticamente
no compite con el canal de duración. La serie barrió el piso (target y precio), el techo, la
estructura de búsqueda (clusters, warm start, multistart), el post-pass y la propia métrica —
pero **nunca el precio del arco en su forma lineal**.

El hueco es concreto y está motivado por un resultado del ciclo anterior:

- `docs/experiments/crossing-metric-validation-20260723.md` construyó `crossings_road`,
  auto-cruces contados sobre la **polilínea real de calles** (`route_audit.road_self_crossings`
  sobre `osrm.fetch_route_path`), frente a `crossings_chord`, que los cuenta sobre cuerdas rectas
  entre paradas. La correlación de Spearman entre ambas es 0,527 global y **−0,575 en
  `reference-n1607`** (invertida). Replicado de forma independiente en
  `floor-price-upper-target-20260723.md` (0,520 / −0,618).
- En ese mismo ciclo, el post-pass 2-opt — que minimiza **travel de red OSRM** y nada más —
  **bajó o empató `crossings_road` en 104 de 108 filas** (−24 % a −45 %), mientras la métrica de
  cuerdas informaba que los multiplicaba por ocho. El "×8" era artefacto de dibujo.

Sobre cuerdas, travel y auto-cruces son ortogonales (r = +0,04). Sobre calle, la evidencia
apunta a que **no** lo son: apretar el travel de red limpia la geometría real. El post-pass lo
consigue reordenando después de resolver. La pregunta abierta es si el **solver** puede
conseguirlo por sí solo subiendo el precio del arco, sin post-pass.

**Hipótesis.** Subir el peso lineal del arco empuja al solver hacia geometrías más ajustadas en
la red, y por tanto baja los auto-cruces **reales** (`crossings_road`).

### Qué NO es este ciclo

`convex_arc_lambda` (celdas `arc-convex-l1/l5/l20`) **ya existe y es otra cosa**: un costo
convexo `travel + λ·max(0, travel − τ)²/τ` que castiga arcos *largos*, ya refutado — los cruces
no son arcos largos. Este ciclo mide el peso **lineal**, que multiplica todo arco por igual y por
tanto reordena la balanza entre el canal de travel y el canal de duración, en vez de deformar la
forma del costo dentro del propio canal de travel. Las dos palancas no se mezclan: todas las
celdas de este ciclo llevan `arc_lambda = 0`.

### Reserva heredada sobre la métrica de cruces

La salida **primaria** de este ciclo es `crossings_road`. `crossings_chord` se publica como
**contexto**, con la reserva explícita de que en `reference-n1607` el orden entre configuraciones
está invertido respecto de la geometría real, medido dos veces de forma independiente. Ninguna
conclusión de este ciclo se apoya en `crossings_chord` en `n=1607`.

## 2. Diseño

**Factor único — `arc_coef` ∈ {1 (control), 3, 10, 30}**, sobre el arm `actual`
(`BALANCE_ARM_ACTUAL`) y el resto de parámetros en sus defaults de producción
(`soft_lower_penalty` 10 000, `soft_upper_target` midpoint, `spatial_span_coef` 3,
`time_span_coef` 0, sin clusters, sin warm start, sin post-pass).

| label | `arc_coef` | precio marginal del segundo de arco |
| --- | ---: | ---: |
| `arc-w1` **(control = `actual`)** | 1 | 1 |
| `arc-w3` | 3 | 3 |
| `arc-w10` | 10 | 10 |
| `arc-w30` | 30 | 30 |

El coeficiente multiplica **solo el travel del evaluador de costo de arco**
(`SetArcCostEvaluatorOfAllVehicles`). **No** entra en `time_callback` ni en la dimensión `Time`.
Esto es una condición de validez del experimento, no un detalle: la dimensión `Time` acota
`T_max` (10 800 s) y alimenta el piso y el techo blandos. Multiplicar ahí cambiaría la semántica
de `T_max` y el experimento no mediría el precio del arco sino una reescala del horizonte.

El tiempo de servicio (120 s por parada) tampoco se multiplica. La suma de servicio de una
solución sin abandonos es constante (`n × 120`), así que multiplicarla no cambiaría la geometría;
lo único que movería es el atractivo relativo de **abandonar** nodos, que es exactamente el
riesgo que este ciclo quiere aislar en el factor y no contaminar.

**Instancias.** Las 12 congeladas de `docs/experiments/instances/`
(`battery-n{50,100,200,400,800,1000}`, `battery-sparse-n{250,500}`,
`area-{26-n157,27-n72,29-n43}`, `reference-n1607`). No se tocan.

**Semillas.** 3 réplicas reales (permutación del orden de nodos; OR-Tools no expone RNG). La `σ`
entre réplicas debe ser > 0 en las celdas no triviales; si sale 0,0 al segundo, las semillas no
llegaron al solver y el cómputo son copias.

**Línea base RE-CORRIDA dentro del ciclo.** La celda `arc-w1` es el control y se corre en esta
misma pasada. No se compara contra medias publicadas por reportes anteriores: el travel de un
mismo brazo se movió 59 971 → 62 751 s entre ciclos, más que su desviación entre semillas, así
que comparar entre reportes no está justificado.

**Persistencia de secuencias.** Cada fila escribe su secuencia de paradas en el
`.sequences.jsonl` contiguo al CSV, como en los dos ciclos anteriores, para poder re-juzgar sin
volver a resolver.

**Presupuesto.** `default_time_limit_sec` de producción. 4 celdas × 12 instancias × 3 semillas =
144 resoluciones, más el cálculo de `crossings_road` vía OSRM por fila.

## 3. Predicciones, escritas antes de correr

1. **Comprobación de cordura del instrumento (obligatoria).** `arc-w1` debe reproducir el
   control **exactamente**: mismo `k`, mismo `travel_sec`, mismos cruces, al segundo, para cada
   par (instancia, semilla). Por construcción el cableado devuelve el mismo callback registrado
   cuando `arc_coef == 1` y `arc_lambda == 0`, así que cualquier diferencia es un error de
   cableado — típicamente el coeficiente filtrándose a `time_callback` — y **no** un hallazgo.
   Si esta comprobación falla, no hay nada que interpretar en el resto de la tabla.
2. **Dirección esperada si la hipótesis es cierta:** `crossings_road` baja de forma monótona (o
   al menos no creciente) al subir `arc_coef`, y `travel_sec` baja también, porque el arco pesa
   más en el objetivo.
3. **Riesgo declarado antes de medir:** el arco compite contra penalizaciones de 500–10 000/s y
   `DROP_PENALTY` es fijo (1 000 000). Un `arc_coef` alto puede empezar a **abandonar árboles**,
   y puede mover `k` al cambiar la balanza entre añadir un vehículo y caminar más. La columna
   `drops` se reporta siempre. **`drops > 0` descarta el brazo**, por bueno que se vea el resto.
4. **Resultado más probable a priori:** plano. Con el piso blando a 10 000/s, incluso 30/s de
   arco sigue siendo dos órdenes de magnitud menor que el subsidio al relleno por debajo de
   `T_min`, así que el canal de duración puede seguir dominando la geometría. Eso también es un
   resultado y se publica.

## 4. Criterio de aceptación a priori

Heredado del ciclo anterior, **no renegociable a posteriori**. Un brazo lo cumple entero o no lo
cumple:

- `reference-n1607`: auto-cruces **−≥30 %** (leídos sobre `crossings_road`, la métrica primaria).
- `reference-n1607`: `travel_sec` **≤ +3 %** contra el control re-corrido.
- `reference-n1607`: `k ≤ 26`.
- Áreas (`area-26-n157`, `area-27-n72`, `area-29-n43`): `relleno_msf` **−≥30 %**.
- Áreas: sin empeorar auto-cruces.
- **`drops = 0`** en toda instancia y semilla.
- `balance ≥ 0,60` en toda instancia.
- 0 rutas degeneradas (umbral absoluto: < 5 paradas **o** < 1 800 s).

Relleno se juzga con `relleno_msf` (contra la cota alcanzable `MSF_k`); `relleno_ub` se publica
como contexto.

Si ningún brazo cumple el criterio completo, **no se cambia ningún default de producción**. Un
brazo que mejora una métrica y empeora otra no es una ganadora parcial: es una ganadora que
falla el criterio, y se reporta así.

## 5. Qué se publica

**Se publica el resultado sea cual sea**, incluido el plano y el monótonamente peor. La tabla
del reporte lista **todas** las celdas, no las que ganaron. Elegir a posteriori la mejor celda y
presentarla como si hubiera sido la hipótesis invalida el ciclo entero.

## 6. Alcance — qué NO hace este ciclo

- No cambia defaults de producción. `arc_coef` queda en 1.
- No toca `docs/experiments/instances/`.
- No mezcla el peso lineal con el costo convexo (`arc_lambda = 0` en todas las celdas).
- No combina `arc_coef` con el post-pass 2-opt: la pregunta es si el **solver** solo consigue lo
  que el post-pass consigue después. Un factorial arco × post-pass es trabajo futuro, no de este
  ciclo.
- No cruza `arc_coef` con otros arms de piso/techo. Un factorial completo del canal de duración
  contra el canal de arco es trabajo futuro.
- No introduce métricas nuevas. `crossings_road` ya existe y está validada en el ciclo anterior.

---

## 7. Resultados

Corrida completa: 144 filas = 12 instancias × 4 celdas × 3 semillas. Todas las semillas llegaron
al solver: `travel_sec` tiene σ > 0 en 47 de los 48 grupos (instancia × celda), y el único grupo
donde las tres réplicas coinciden es `area-27-n72` / `arc-w10`, donde convergen a la misma
partición (`k=2`, 5 731 s las tres) pero difieren en `crossings_road` (11/11/16), así que tampoco
son copias. Medias ± σ **poblacional** entre las 3 semillas.

**Comprobación de cordura del instrumento — PASA.** Con `arc_coef = 1` y `arc_lambda = 0` el
solver registra como evaluador de arco **el mismo objeto callback** que la dimensión `Time`
(`arc_cb_index = time_cb_index`), no una copia reponderada: la celda `arc-w1` es el control por
construcción del código, no por coincidencia numérica. Las dos condiciones que podían romperlo
están pinchadas por test: `arc_coef=1` reproduce la solución del default, y una ruta dimensionada
para llenar exactamente `T_max` sigue sin abandonos a `arc_coef=10` — si el coeficiente se filtrara
a `time_callback`, el cumul se pasaría de `T_max` y el solver abandonaría nodos. El resto de la
tabla es interpretable.

### 7.1 Salida primaria — `crossings_road`

| instancia | arc-w1 | arc-w3 | arc-w10 | arc-w30 |
| --- | --- | --- | --- | --- |
| battery-n50 | 3,3 ± 2,5 | 3,3 ± 1,2 (+0 %) | 1,3 ± 1,2 (−60 %) | 1,3 ± 0,5 (−60 %) |
| battery-n100 | 9,3 ± 3,8 | 6,7 ± 4,5 (−29 %) | 4,0 ± 1,4 (−57 %) | 2,7 ± 0,5 (−71 %) |
| battery-n200 | 11,7 ± 4,6 | 9,0 ± 0,8 (−23 %) | 8,7 ± 1,7 (−26 %) | 6,0 ± 2,2 (−49 %) |
| battery-n400 | 17,7 ± 0,5 | 16,3 ± 4,5 (−8 %) | 16,0 ± 3,6 (−9 %) | 19,0 ± 14,2 (+8 %) |
| battery-n800 | 22,3 ± 4,8 | 19,0 ± 9,4 (−15 %) | 19,3 ± 4,9 (−13 %) | 25,7 ± 7,6 (+15 %) |
| battery-n1000 | 47,3 ± 2,6 | 31,0 ± 2,2 (−35 %) | 23,7 ± 6,2 (−50 %) | 23,0 ± 0,0 (−51 %) |
| battery-sparse-n250 | 6,3 ± 1,2 | 5,0 ± 1,4 (−21 %) | 3,7 ± 1,2 (−42 %) | 2,7 ± 0,5 (−58 %) |
| battery-sparse-n500 | 6,3 ± 1,7 | 5,7 ± 1,2 (−11 %) | 7,7 ± 0,5 (+21 %) | 9,7 ± 0,9 (+53 %) |
| area-26-n157 | 8,7 ± 0,9 | 5,7 ± 0,9 (−35 %) | 5,7 ± 2,5 (−35 %) | 5,0 ± 0,0 (−42 %) |
| area-27-n72 | 12,7 ± 5,2 | 9,0 ± 4,1 (−29 %) | 12,7 ± 2,4 (+0 %) | 10,3 ± 1,2 (−18 %) |
| area-29-n43 | 7,7 ± 5,4 | 7,7 ± 0,9 (+0 %) | 3,7 ± 2,9 (−52 %) | 8,0 ± 3,6 (+4 %) |
| **reference-n1607** | **40,7 ± 4,8** | **39,0 ± 4,2 (−4 %)** | **32,3 ± 0,9 (−20 %)** | **41,3 ± 6,9 (+2 %)** |

En la instancia del criterio (`reference-n1607`) el mejor brazo es `arc-w10` con **−20 %**, por
debajo del umbral **−30 %**; `arc-w30` **revierte** a +2 %. La predicción 2 (descenso monótono)
queda **falsada**: hay un óptimo intermedio (~w10) y luego el travel forzado empeora la geometría.
El mismo patrón de reversión aparece en `battery-n400/n800/sparse-n500`.

### 7.2 `travel_sec`, `k`, `drops`, `degenerate`, `balance` (instancias del criterio)

| celda | travel n1607 | k n1607 | drops | degen n1607 | balance n1607 |
| --- | --- | --- | --- | --- | --- |
| arc-w1 | 59 937 ± 1 088 | 25,0 | **0** en toda la tabla | 0,0 | 0,846 |
| arc-w3 | 59 889 (−0 %) | 24,7 | **0** | 0,0 | 0,850 |
| arc-w10 | 59 300 (−1 %) | 24,0 | **0** | **0,3 ± 0,5** | 0,881 |
| arc-w30 | 61 327 (+2 %) | 24,7 | **0** | **0,3 ± 0,5** | 0,838 |

`drops = 0` en las 144 filas: el riesgo declarado (abandono de árboles por precio de arco alto
contra `DROP_PENALTY` fijo) **no se materializó** ni a w30. Pero `arc-w10` y `arc-w30` introducen
**una ruta degenerada** en 1 de 3 semillas de `n1607` (0 en el control), lo que ya viola el
criterio de 0 degeneradas con independencia de los cruces.

### 7.3 Relleno — `relleno_msf` (primaria) y `relleno_ub` (contexto), áreas y n1607

| instancia | métrica | arc-w1 | arc-w3 | arc-w10 | arc-w30 |
| --- | --- | --- | --- | --- | --- |
| area-26-n157 | relleno_msf | 1 440 | −3 % | **−20 %** | −15 % |
| area-27-n72 | relleno_msf | 4 821 | −0 % | −0 % | −0 % |
| area-29-n43 | relleno_msf | 1 242 | −0 % | −1 % | −1 % |
| reference-n1607 | relleno_msf | 29 114 | −0 % | −3 % | +5 % |
| area-26-n157 | relleno_ub | 768 | −6 % | −37 % | −28 % |
| area-27-n72 | relleno_ub | 4 699 | −0 % | −0 % | −0 % |
| area-29-n43 | relleno_ub | 1 076 | −0 % | −1 % | −1 % |
| reference-n1607 | relleno_ub | 20 242 | −1 % | −4 % | +7 % |

El relleno de áreas **no** baja −30 % en `relleno_msf` (primaria): `area-26` llega a −20 % en
w10, `area-27` y `area-29` son planas. Es la geometría irreducible ya establecida por la serie —
`area-27` (`k=2`) y `area-29` (`k=1`) están al piso alcanzable y no hay relleno que quitar. Nota:
en `relleno_ub` (contexto) `area-26` **sí** cruza −30 % (−37 % en w10), pero la métrica que juzga
es `relleno_msf`.

### 7.4 `crossings_chord` (contexto, con reserva en n1607)

Sobre cuerdas el arco **sube** los cruces en la mayoría de las battery densas (n200 +325 %, n400
+305 % a w30) mientras los baja sobre calle — la disociación cuerda↔calle del ciclo anterior,
otra vez. En `reference-n1607` `crossings_chord` es plano (±4 %) y su orden está invertido
respecto de `crossings_road`, como quedó documentado; ninguna conclusión se apoya en él aquí.

## 8. Veredicto

**El peso lineal del arco NO cumple el criterio de aceptación. No se cambia ningún default;
`arc_coef` queda en 1.**

Contra la instancia del criterio (`reference-n1607`), tres cláusulas fallan:

1. **Auto-cruces de calle:** mejor brazo `arc-w10` a **−20 %**, no llega a −30 %; `arc-w30`
   revierte a +2 %.
2. **Rutas degeneradas:** `arc-w10` y `arc-w30` generan 1 ruta degenerada en 1/3 semillas; se
   exige 0.
3. **Relleno de áreas:** `relleno_msf` no baja −30 % (mejor −20 % en `area-26`; `area-27`/`area-29`
   son piso irreducible).

`travel ≤ +3 %`, `k ≤ 26`, `balance ≥ 0,60` y `drops = 0` **sí** se cumplen en n1607 hasta w30,
pero un brazo que cumple parte del criterio y falla otra parte **falla el criterio**.

**Hallazgo honesto, no la hipótesis re-etiquetada.** El peso lineal del arco **sí** es una palanca
real de `crossings_road` donde el travel tiene holgura: en las battery densas baja los cruces de
calle **y** el travel a la vez (`battery-n1000` −50 % cruces / −13 % travel; `battery-n100` −71 %
/ −10 %). Pero la instancia operativa (`reference-n1607`, 11,9 km, dos fuentes agregadas) y las
áreas reales están cerca de su piso de travel alcanzable: ahí el arco no tiene margen que apretar,
se estanca en ~−20 % y a w30 empieza a **añadir** travel y a degradar la geometría. La palanca
existe pero no en el régimen donde vive el criterio.

Esto es consistente con el resultado del ciclo anterior: el post-pass 2-opt baja `crossings_road`
reordenando **después** de resolver, sin forzar más travel; el precio de arco intenta lo mismo
**dentro** del solver pero, como cualquier término aditivo por arco, sólo puede comprar geometría
pagando travel, y en el régimen saturado ese precio se vuelve contraproducente. La vía que sí
mejora Pareto sigue siendo el post-pass, no el precio del arco.

### Qué queda descartado

El **peso lineal del arco como palanca de auto-cruces reales de calle en el régimen operativo**
queda descartado: falla el criterio en `reference-n1607` por tres cláusulas y revierte a fuerza
alta. No reabrir sin dato nuevo. Queda **abierto** como observación, no como propuesta a adoptar:
en instancias con holgura de travel el arco lineal es una mejora conjunta de cruces y travel; si
alguna vez el régimen objetivo se mueve a esa zona, el brazo ~w10 es el candidato. El factorial
arco × post-pass y arco × arms de piso queda como trabajo futuro explícito, fuera de este ciclo.
