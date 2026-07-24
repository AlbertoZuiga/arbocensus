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

Pendiente: se completa tras la corrida, sin tocar las secciones anteriores.
