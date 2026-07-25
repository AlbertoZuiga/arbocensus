# Flota asimétrica: eximir una ruta del piso o del techo blando de duración

**Fecha:** 2026-07-25
**Estado al commitear esta sección:** pre-registro. Motivación, diseño, celdas, instancias,
métricas, predicciones, comprobaciones de cordura y criterio de aceptación se commitean **antes**
de medir nada. Los resultados se agregan después, sin tocar nada de lo anterior; cualquier
desviación se declara como tal.

La configuración de producción del solver **no cambia**: las celdas nuevas son brazos opt-in del
driver de barrido, y el brazo de producción (`actual`) queda intacto bit a bit. Su adopción, si
alguna cumpliera el criterio completo, sería un cambio aparte.

---

## 1. Motivación

Hoy los `max_vehicles` del modelo son **intercambiables**: cada vehículo recibe exactamente las
mismas cotas blandas de duración sobre su cumul final — piso `T_min` = 7 200 s a 10 000/s y techo
en el punto medio (9 000 s) a 500/s. La serie barrió el **nivel** de esas cotas (`tmin-scaled`,
`feasible-floor-b*`, `no-floor*`, `upper@T_max`) y su **precio** (`floor{10000,2000,500,100}`),
siempre aplicando el mismo valor a **toda** la flota. Nunca midió una flota **asimétrica**: mismos
precios, pero con **una** ruta eximida de una de las dos cotas.

### Descomposición aritmética del objetivo — NO es un mecanismo predictivo

Con los defaults de producción, el precio marginal de un segundo extra de caminata en una ruta
depende de dónde esté su cumul final (`.claude/rules/ortools-vrp.md`, "Marginal price, not nominal
weight"):

| cumul final de la ruta | precio de +1 s de viaje |
| --- | ---: |
| bajo `T_min` (7 200 s) | **−9 999** (el modelo *paga* por rellenar) |
| entre `T_min` y el punto medio (9 000 s) | **+1** |
| sobre el punto medio | **+501** |

Y abrir un vehículo más cuesta `FIXED_VEHICLE_COST` = 100 000, mientras que descargar el exceso de
una ruta saturada ahorra hasta `9 000 × 500 = 4 500 000` de cargo por techo. La razón entre ambos
es ~44:1. **Aritméticamente**, entonces: cuando una ruta pasa del punto medio, la salida más barata
del modelo es abrir otra ruta; y cuando el trabajo total no alcanza para llenar `k · T_min`,
rellenar es óptimo, no un defecto de búsqueda.

De ahí sale la idea de los dos **sumideros**:

- una ruta **eximida del techo** absorbe el exceso sin exigir un vehículo nuevo → `k` debería bajar
  o quedar igual;
- una ruta **eximida del piso** absorbe el residuo sin obligar al resto a paddear hasta `T_min`.

Son complementarios: una ruta larga, una corta, y `k−2` dentro de la banda.

**Esto es una descomposición aritmética de la función objetivo, no un mecanismo predictivo.** La
distinción no es retórica: la predicción operativa derivada de esta misma estructura de precios ya
**falló una vez** en esta serie. `regime-guard-20260724.md` construyó el predicado `rho_pad` a
partir de exactamente este marco, predijo que el relleno sería irreducible donde el piso es
infactible y reducible donde no, y acertó **3 de 12** instancias contra **8 de 12** de la regla
trivial "gana siempre el control", con correlación de Spearman −0,039 entre el predicado y lo que
había para ganar. La aritmética del objetivo es correcta; lo que no está establecido es que
prediga el comportamiento del solver. Este ciclo la usa para **elegir qué medir**, nunca como
evidencia de qué va a pasar.

### Apoyo indirecto, declarado como post-hoc de otro ciclo

`regime-guard-20260724.md` cerró con una observación explícitamente marcada como post-hoc y **no
probada**: las dos instancias con caídas grandes de relleno (`area-27` −96,3 %, `battery-n50`
−89,5 %) son exactamente aquellas donde el brazo que sube el techo a `T_max` **elimina una ruta**.
Eximir del techo a **una sola** ruta es la perturbación mínima de ese efecto: mueve el techo de un
vehículo en vez de los `max_vehicles`. Ese es el hueco concreto que este ciclo llena. Sigue siendo
una observación post-hoc de otro ciclo, y no cuenta como predicción a favor.

### Reapertura declarada de `exempt-last`

El brazo `tmin-scaled+exempt-last` **ya existe** en el código y fue descartado en el barrido de
2026-07-18. Ese descarte **no se sostiene bajo el criterio de hoy**, por tres razones
independientes:

1. Se juzgó contra una compuerta de balance **≥ 0,80**; la compuerta vigente es **≥ 0,60**, contra
   la que el brazo no falla en ninguna de las 12 instancias.
2. Se juzgó con `crossings_chord`, métrica establecida después como proxy parcial (ρ = 0,527) y
   con el **orden invertido** en `reference-n1607` (ρ = −0,575), replicado de forma independiente
   (0,520 / −0,618). Su único fallo vivo era −2,2 % de cruces en `reference-n1607`, medido en la
   columna equivocada.
3. Se corrió **sin semillas reales**: el defecto de instrumentación cerrado en el barrido de
   2026-07-20 hacía que las tres "réplicas" fueran copias de una misma corrida.

Por lo tanto **`exempt-lower` es `exempt-last` re-medido**, con dos diferencias declaradas por
adelantado: se aplica sobre el brazo de producción (`actual`, piso `T_min` = 7 200 s) en vez del
brazo `tmin-scaled` (piso escalado `min(T_min, servicio_total/max_vehicles)`), y exime a un
vehículo **activo** en vez del último índice (§2.2). El reporte lo dirá así.

---

## 2. Diseño

### 2.1 Factorial 2×2

Factor A: eximir a una ruta del **piso** blando. Factor B: eximir a una ruta del **techo** blando.
Todo lo demás en defaults de producción: brazo `actual`, `soft_lower_penalty` 10 000,
`soft_upper_penalty` 500, techo en el punto medio, `spatial_span_coef` 3, `time_span_coef` 0,
`arc_coef` 1, sin clusters, sin warm start, estrategia `spatial_term`, post-pass 2-opt activo (es
default del pipeline desde 2026-07-24 y corre dentro de `_persist_solution`).

| celda | piso blando | techo blando |
| --- | --- | --- |
| `control` (= `actual`, línea base re-corrida) | todos los vehículos | todos los vehículos |
| `exempt-lower` | **un vehículo exento** | todos |
| `exempt-upper` | todos | **un vehículo exento** |
| `exempt-both` | **un vehículo exento** | **otro vehículo exento** |

`control` **no** es la media publicada por ningún reporte anterior: se re-corre dentro de este
ciclo. La varianza entre corridas es mayor que la varianza entre semillas de una misma corrida —
el travel del mismo brazo se movió 59 971 → 62 751 s entre ciclos, más que su σ entre semillas.

### 2.2 Qué vehículo se exime, y por qué no el último

`max_vehicles` **no** es la flota: es una cota superior holgada,
`ceil(trabajo_total / T_min) + 5`. En `reference-n1607` da ≈ 36 vehículos contra `k` = 25 rutas
reales, es decir **once vehículos inactivos**. Y un vehículo vacío no paga ni el costo fijo ni
ninguna cota blanda (`.claude/rules/ortools-vrp.md`): **eximir a un vehículo inactivo es
literalmente inerte**, y se mediría como un nulo indistinguible de "la palanca no sirve".

Esa es la explicación candidata del nulo de `exempt-last`, que exime al índice
`max_vehicles − 1` — el candidato más probable a quedar vacío. Este ciclo la **confirma o la
descarta con dato**, no la asume (§2.5).

Por eso las celdas nuevas eximen a **índices bajos**: `PATH_CHEAPEST_ARC` construye las rutas
vehículo por vehículo desde el 0, así que los índices bajos son los que se llenan.

- vehículo **0** → sumidero largo: exento del **techo**.
- vehículo **1** → sumidero corto: exento del **piso**.

En `exempt-both` los dos roles caen en vehículos distintos, que es la forma "una larga + una corta
+ `k−2` en la banda" de la hipótesis.

Esto **no garantiza** que el vehículo exento resulte activo, y por eso cada fila del CSV publica
qué vehículos se eximieron y **cuáles de ellos quedaron activos** en la solución. El reporte
publica el conteo de exenciones que cayeron en un vehículo inactivo, por celda e instancia.

### 2.3 Instancias y semillas

Las **12 instancias congeladas** de `docs/experiments/instances/`, exactamente el mismo conjunto
que los dos ciclos anteriores, sin tocar el directorio:
`battery-n{50,100,200,400,800,1000}`, `battery-sparse-n{250,500}`,
`area-{26-n157,27-n72,29-n43}`, `reference-n1607`.

**3 semillas reales** por celda × instancia (`SEEDS = [1, 2, 3]`). OR-Tools no expone RNG: la
réplica se obtiene permutando el orden de nodos, lo que cambia el desempate de
`PATH_CHEAPEST_ARC` y la trayectoria del GLS. La σ entre réplicas debe ser > 0 en las celdas no
triviales; si las tres réplicas devuelven cifras idénticas al segundo, las semillas no llegaron al
solver, la corrida son copias y **se aborta y se arregla** en vez de interpretarse.

4 celdas × 12 instancias × 3 semillas = **144 filas**, más las dos celdas de control de
instrumento de §2.5.

### 2.4 Métricas y sus trampas

- **Salida primaria: `crossings_road`** — autocruces contados sobre la polilínea real de calles
  (`road_self_crossings` sobre `fetch_route_paths`). `crossings_chord` se publica **solo como
  contexto**: es un proxy parcial (ρ = 0,527) y está **invertido** en `reference-n1607`
  (ρ = −0,575), medido dos veces de forma independiente. Un ciclo juzgado por cuerdas ya estuvo a
  punto de meter un cambio malo a producción. Ninguna conclusión se apoya en cuerdas.
- **`crossings` es intra-ruta.** No se confunde con `interleave_per_route`, que mide solapamiento
  **entre** rutas distintas y va como contexto.
- **Relleno: `relleno_msf`** contra la cota alcanzable `MSF_k`, en las instancias de área.
  `relleno_ub` va como contexto.
- **Duración: `dur_min` / `dur_median` / `dur_max` y `k`** se publican por celda, siempre. Son la
  lectura directa de si la asimetría produjo el sumidero que se buscaba o una flota degenerada.
- **`T_max` sigue siendo capacidad DURA** de la dimensión `Time` (10 800 s). Eximir del techo
  **blando** no la toca: ninguna celda de este ciclo permite una ruta sobre `T_max`. Son dos cosas
  distintas y el reporte no las mezcla.

**Degeneración: solo por duración (< 1 800 s).** El segundo criterio histórico ("< 5 paradas")
queda eliminado por decisión explícita, así que la columna `degenerate_routes` de este ciclo
cuenta **solo** rutas cortas en tiempo. El conteo de rutas con < 5 paradas se sigue publicando
como columna separada de contexto (`short_routes`). Desviación declarada: la columna
`degenerate_routes` de los CSV de ciclos anteriores codificaba las dos condiciones, así que **no
es comparable fila a fila con la de este CSV**; dentro de este ciclo todas las celdas se miden con
la misma regla.

**Balance: se publican las dos lecturas, y el criterio se juzga con la NO excluyente.**
`balance` = `min(duración) / max(duración)` sobre **todas** las rutas.
`balance_excl_min` = lo mismo tras descartar la ruta más corta. El brazo histórico
`tmin-scaled+exempt-last` excluye la ruta residual del balance
(`config_algorithm_sweep.py`, `_balance`); **las celdas nuevas no heredan esa exclusión**: se
juzgan con la misma regla que el control, que es la conservadora, y la lectura excluyente se
publica al lado en todas las tablas. Una celda que solo pasa la compuerta bajo la lectura
excluyente **falla el criterio**, y el reporte lo dirá así. La razón de no heredarla es que el
balance es la compuerta que de hecho mata candidatos en esta serie: relajar su definición para el
brazo que la necesita sería elegir la regla después de ver el resultado.

### 2.5 Comprobaciones de cordura del instrumento

Dos celdas extra cuyo resultado se conoce **por construcción**. Si cualquiera falla, la
implementación está mal y **no hay nada que interpretar** en el resto de la tabla: se para y se
arregla.

**C1 — `exempt-none` ≡ `control`, exactamente.** Es la maquinaria de exención con el conjunto de
vehículos exentos **vacío**: recorre el mismo camino de código nuevo, pero registra sobre cada
vehículo las mismas cotas que el brazo `actual`. Debe reproducir `control` **al segundo** — mismo
`k`, mismo `travel_sec`, mismos cruces — para cada par (instancia, semilla). Cualquier diferencia
es error de cableado (un off-by-one en el bucle de vehículos, la exención filtrándose a todos, la
semilla no llegando al solver) y **no** un hallazgo. Se corre sobre
`reference-n1607`, `area-26-n157` y `battery-n100` × 3 semillas = 9 filas. Se complementa con un
test puro de equivalencia exacta de `vehicle_bounds` entre `exempt-none` y `actual` para **todos**
los índices de vehículo, que no necesita solver.

**C2 — `exempt-lower-last`, la exención en el último índice.** Idéntica a `exempt-lower` salvo que
exime al vehículo `max_vehicles − 1`, que es a quien apuntaba el `exempt-last` histórico. Su
resultado esperado por construcción es **inerte si ese vehículo queda inactivo**, porque un
vehículo vacío no paga ninguna cota blanda. Junto con la columna que reporta la actividad del
vehículo exento, esta celda confirma o descarta **dentro de este ciclo** la explicación candidata
del nulo previo. Se corre sobre `reference-n1607`, `battery-n1000`, `battery-n400` y
`area-26-n157` × 3 semillas = 12 filas: las cuatro instancias con `k ≥ 2` y holgura grande entre
`k` y `max_vehicles`, que es donde la explicación es comprobable.

Nota honesta sobre una comprobación que **no** se usa: "una instancia donde ninguna ruta cae bajo
`T_min` ⟹ `exempt-lower` es inerte" **no es válida por construcción**, y por eso no se registra
como tal. Quitarle el piso a un vehículo no solo perdona un déficit existente: abre soluciones
nuevas donde ese vehículo *sí* baja del piso y se ahorra el cargo. En una instancia con `k` = 1
(`area-29-n43`) el modelo puede mover toda la carga al vehículo exento y escapar del piso por
completo. Eso es efecto real de la palanca, no un fallo de instrumento, y confundirlo con una
comprobación de cordura habría producido una falsa alarma.

### 2.6 Presupuesto

`default_time_limit_sec` de producción (`min(30 + 1,5·n, 120)` s), `starts = 1`.
144 + 9 + 12 = **165 resoluciones**, más el cálculo de `crossings_road` vía OSRM por fila.

---

## 3. Predicciones, escritas antes de correr

1. **C1 (cordura, obligatoria).** `exempt-none` reproduce `control` al segundo en las 9 filas. Si
   falla, se para.
2. **C2 (cordura, obligatoria).** En las filas de `exempt-lower-last` donde la columna de
   diagnóstico diga que el vehículo `max_vehicles − 1` quedó **inactivo**, la fila es idéntica al
   `control` de la misma instancia y semilla. Si el vehículo resulta inactivo en la mayoría de las
   filas, la explicación candidata del nulo de `exempt-last` queda **confirmada**; si resulta
   activo, queda **descartada** y el nulo previo hay que atribuirlo a otra cosa.
3. **Dirección esperada si la hipótesis es cierta.** `exempt-upper` deja `k` igual o menor que el
   control y baja `crossings_road`; `exempt-lower` baja `relleno_msf` en las instancias de área
   sin subir `k`; `exempt-both` combina ambos efectos.
4. **Riesgo declarado por adelantado.** `exempt-upper` puede degenerar en "una ruta gigante y el
   resto vacías": es la mitad del mecanismo ya observado en otro brazo de esta serie, donde `k`
   pasó de 25 a 34 y el travel subió +59 %. Sus falsadores son **travel > +3 %** o
   **balance < 0,60**. Simétricamente, `exempt-lower` puede producir una ruta residual corta: la
   captura la compuerta de 0 rutas degeneradas por duración.
5. **Resultado más probable a priori: plano o negativo.** Trece ciclos de esta serie buscaron una
   configuración ganadora global y ninguno la encontró; los dos anteriores (guard de régimen, peso
   lineal del arco) cerraron en negativo. Nada obliga a que este sea distinto, y el plano también
   se publica.

---

## 4. Criterio de aceptación a priori

Heredado, **no renegociable a posteriori**. Un brazo lo cumple **entero** o no lo cumple:

- `reference-n1607`: `crossings_road` **−≥ 30 %** contra el control re-corrido.
- `reference-n1607`: `travel_sec` **≤ +3 %**.
- `reference-n1607`: `k ≤ 26`.
- Áreas (`area-26-n157`, `area-27-n72`, `area-29-n43`): `relleno_msf` **−≥ 30 %**.
- Áreas: `crossings_road` sin empeorar.
- Todas las instancias: **`drops` = 0**.
- Todas las instancias: **`balance` ≥ 0,60**, leído sin excluir ninguna ruta (§2.4).
- Todas las instancias: **0 rutas degeneradas por duración** (< 1 800 s).

Lecturas ya medidas que ayudan a interpretar, y que se declaran ahora para no descubrirlas
después: en esta serie el ítem de **cruces nunca fue el binding** — lo que mata candidatos es
**balance** —, y el ítem de travel es de **no empeorar**, no de mejorar.

Si ninguna celda cumple el criterio completo, **no se cambia ningún default de producción**. Un
brazo que mejora una métrica y empeora otra **no es una ganadora parcial**: es una ganadora que
falla el criterio, y se reporta así.

---

## 5. Qué se publica

**Se publica el resultado sea cual sea**, incluido el plano, el negativo y el monótonamente peor.
La tabla del reporte lista **todas** las celdas, no las que ganaron: elegir la mejor celda a
posteriori y presentarla como si hubiera sido la hipótesis invalida el ciclo entero. Se publican
medias **con σ poblacional** entre las 3 semillas, y una diferencia menor o igual a la mayor de
las dos σ **no es una diferencia**.

---

## 6. Alcance — qué NO hace este ciclo

- **No cambia defaults de producción.** El brazo `actual` queda intacto; las exenciones son brazos
  opt-in del driver de barrido. Si alguna celda cumpliera el criterio completo, su adopción sería
  un cambio aparte con su propia línea base.
- No toca `docs/experiments/instances/` (suite congelada), ni el post-pass 2-opt, ni los clusters,
  ni el warm start, ni el precio del arco.
- No barre **cuántos** vehículos se eximen: exactamente uno por cota. Un barrido sobre el número
  de sumideros es trabajo futuro.
- No barre **el precio** de las cotas: los precios quedan en 10 000/s y 500/s. El factorial
  precio × asimetría es trabajo futuro.
- No mueve `T_max`, que sigue siendo capacidad dura.
- No cambia el brazo histórico `tmin-scaled+exempt-last` ni su convención de balance excluyente:
  se deja como está para no romper la comparabilidad de los CSV anteriores.
- No introduce métricas nuevas: `crossings_road`, `relleno_msf` y `balance` ya existen. Lo único
  que se agrega son columnas de diagnóstico (vehículos exentos, actividad de esos vehículos,
  `max_vehicles` estimado, balance excluyente, conteo de rutas con < 5 paradas).
- No adopta `crossings_road` como criterio oficial de la serie: lo usa como salida primaria de
  este ciclo, con la justificación de §2.4.
