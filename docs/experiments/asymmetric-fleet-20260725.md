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

---

## 7. Resultados

Corrida completa: **165 filas** = 4 celdas × 12 instancias × 3 semillas (144) + `exempt-none` sobre
3 instancias × 3 semillas (9) + `exempt-lower-last` sobre 4 instancias × 3 semillas (12). Datos en
`asymmetric-fleet-20260725.csv`; secuencias de paradas en el `.sequences.jsonl` contiguo. Medias ±
σ **poblacional** entre las 3 semillas. Cero `drops` en las 165 filas.

**Desviaciones respecto del pre-registro:** dos, ambas declaradas abajo en el punto donde ocurren.
(1) La forma literal de C2 ("fila idéntica al control cuando el vehículo queda inactivo") resultó
inaplicable, y el motivo es un hallazgo del ciclo, no una excusa (§7.3). (2) Se agregó una corrida
de **replicación del control** que el pre-registro no contemplaba, forzada por el resultado de C1
(§7.2). Nada más se movió: ni celdas, ni instancias, ni métricas, ni el criterio.

### 7.1 Semillas: llegaron al solver

σ(`travel_sec`) > 0 en **50 de los 55** grupos (celda × instancia) con más de una semilla. Los 5
grupos con σ = 0 son instancias donde el brazo converge a la misma partición desde los tres órdenes
de entrada (`exempt-lower`/`area-29`, `exempt-upper`/`battery-n50`, `exempt-both`/`battery-n50`,
`area-27`, `area-29`) — todas de `k ≤ 2`, donde el espacio de particiones es diminuto. No son
copias del mismo cómputo: el resto de la tabla tiene dispersión, y en `reference-n1607` la σ de
travel es ~1 200–1 450 s.

### 7.2 C1 — `exempt-none` contra `control`: PASA, y de paso mide el piso de ruido

| instancia | semillas idénticas al segundo |
| --- | --- |
| `area-26-n157` | **3 de 3** |
| `battery-n100` | **3 de 3** |
| `reference-n1607` | **1 de 3** |

Siete de nueve filas reproducen el control **exactamente** (fila completa, incluida la secuencia de
paradas). Las dos de `reference-n1607` que no lo hacen difieren en travel **−0,02 %** y **+0,17 %**,
con `k` = 25 y `balance` idénticos en ambas.

Eso no basta para declarar el instrumento sano, así que se corrió la comprobación que decide:
**re-correr el `control` contra sí mismo**, misma celda, mismas semillas, mismo código, en
`reference-n1607` (`asymmetric-fleet-20260725-replication.csv`).

| semilla | travel corrida A | travel corrida B | Δ | `crossings_road` A → B | `k` | `balance` A → B |
| ---: | ---: | ---: | ---: | :-: | :-: | :-: |
| 1 | 58 666 | 58 622 | **−0,08 %** | 31 → 30 | 25 | 0,824 → 0,824 |
| 2 | 60 609 | 60 715 | **+0,17 %** | 42 → 42 | 25 | 0,846 → 0,846 |
| 3 | 57 690 | 57 159 | **−0,92 %** | 31 → 30 | 25 | 0,848 → 0,838 |

**El control no se reproduce a sí mismo en `reference-n1607`.** El GLS se corta por reloj de pared
(`time_limit.FromSeconds`, 120 s), no por número de iteraciones, así que dos corridas del mismo
modelo devuelven incumbentes distintos según dónde caiga el deadline. A `n` = 1 607 eso vale hasta
**0,92 %** de travel y ±1 auto-cruce; en instancias chicas la búsqueda converge antes del corte y
la reproducción es exacta, que es justamente lo que muestran `area-26` y `battery-n100`.

Conclusión del instrumento: `exempt-none` **pasa**. Su desviación máxima (0,17 %) es menor que la
del control contra sí mismo (0,92 %), y el modelo es idéntico por construcción del código —
`exempt_vehicles()` devuelve `(None, None)` y `vehicle_bounds` reproduce las tuplas del brazo
`actual` para todo `vehicle_id`, verificado por test unitario sin solver.

**Consecuencia que gobierna toda lectura de `reference-n1607` en este reporte:** el piso de ruido
de re-ejecución es **≈1 % de travel y ±1 auto-cruce**. Cualquier diferencia menor que eso no es una
diferencia. Se declara antes de leer las celdas, no después.

### 7.3 C2 — la trampa del vehículo inactivo: la explicación candidata queda REFUTADA

El pre-registro predijo que `exempt-lower-last` sería inerte porque el vehículo `max_vehicles − 1`
quedaría vacío, y que eso explicaría el nulo del descarte histórico. **Lo medido es lo contrario:**

| instancia | vehículo exento | flota | inactivo en |
| --- | :-: | :-: | :-: |
| `reference-n1607` | v35 | 36 | **0 de 3** |
| `battery-n1000` | v23 | 24 | **0 de 3** |
| `battery-n400` | v12 | 13 | **0 de 3** |
| `area-26-n157` | v7 | 8 | **0 de 3** |

**12 de 12 filas: el último vehículo está ACTIVO.** La explicación candidata del nulo previo —
"la exención cayó en un vehículo que el solver nunca usa" — **no se sostiene**, y queda descartada
dentro de este ciclo, como el pre-registro exigía. El nulo de `exempt-last` hay que atribuirlo a
otra cosa, y la §7.6 dice a qué.

Desviación declarada: la forma literal de C2 ("si el vehículo queda inactivo, la fila es idéntica
al control") **nunca pudo evaluarse**, porque su antecedente es falso en las 12 filas. Y de haberlo
sido, tampoco habría sido válida: ya en el humo de `area-29` una exención sobre un vehículo
inactivo dio travel 1 069 contra 997 del control. Una exención inerte **en el objetivo** no es
inerte **en la búsqueda**: cambia el precio de las soluciones vecinas que sí usarían ese vehículo,
y con ello la trayectoria del GLS. La comprobación estaba mal formulada en el pre-registro y se
reporta así en vez de reescribirla.

Lo que sí queda medido, y es el diagnóstico de verdad, es **cuándo el solver usa el sumidero**:

| celda | exenciones que cayeron en vehículo inactivo |
| --- | ---: |
| `exempt-lower` | **21 de 36** |
| `exempt-upper` | **14 de 36** |
| `exempt-both` | **35 de 72** |
| `exempt-lower-last` | **0 de 12** |

Y el reparto no es aleatorio. Cruzando con la duración mínima de ruta del control (media entre las
tres semillas):

| régimen del control | instancias | `exempt-lower` inactivo |
| --- | --- | :-: |
| `dur_min` **sobre** `T_min` (el piso no cobra) | `area-26`, `battery-n100/200/800/1000`, `n1607` | **3/3 en todas** |
| `dur_min` **sobre** `T_min`, pero mezclado | `battery-n400`, `sparse-n500` | 2/3 y **1/3** |
| `dur_min` **bajo** `T_min` (el piso cobra) | `area-27`, `area-29`, `battery-n50`, `sparse-n250` | **0/3 en todas** |

La dirección se sostiene, pero **no es 12 de 12**: de las 24 filas del régimen "el piso no cobra",
**21** dejan el vehículo exento ocioso; de las 12 filas del régimen "el piso cobra", **las 12** lo
usan. Leído fila a fila —`dur_min` del control de *esa* semilla contra el uso del sumidero en *esa*
semilla— la correspondencia es **31 de 36**, con cinco excepciones en ambas direcciones:
`area-26`/s2 (`dur_min` 6 974 s, bajo el piso, y aun así ocioso), `battery-n100`/s2 (7 196 s,
ídem), `battery-n400`/s3 (9 034 s, sobre el piso y sin embargo usado) y `sparse-n500`/s1 y s2
(9 079 y 8 861 s, ídem). Por instancia, **10 de 12** son limpias (0/3 o 3/3) y 2 quedan mezcladas.

Donde ninguna ruta cae bajo el piso, el piso no está cobrando nada, así que no hay déficit que
perdonar y el solver **tiende a** dejar el vehículo exento vacío: la palanca no tiene de dónde
agarrar. Donde sí cobra, el solver usa el sumidero en las tres semillas, sin excepción. Es la
regularidad más fuerte del ciclo y **su resultado principal**, más que cualquier celda — pero es
una tendencia, no una ley, y las cinco filas discordantes se publican en vez de redondearse.

### 7.4 Salida primaria — `crossings_road` (media ± σ, Δ vs control re-corrido)

| instancia | `control` | `exempt-lower` | `exempt-upper` | `exempt-both` |
| --- | --- | --- | --- | --- |
| `battery-n50` | 1,3 ± 0,9 | 0,7 ± 0,5 (−50 %) | 1,0 ± 0,0 (−25 %) | 1,0 ± 0,0 (−25 %) |
| `battery-n100` | 3,7 ± 0,5 | 3,7 ± 0,5 (+0 %) | 3,3 ± 0,5 (−9 %) | 3,3 ± 0,5 (−9 %) |
| `battery-n200` | 11,7 ± 2,1 | 11,3 ± 1,7 (−3 %) | 11,7 ± 2,1 (+0 %) | 11,7 ± 2,1 (+0 %) |
| `battery-n400` | 15,3 ± 1,9 | 15,7 ± 2,4 (+2 %) | 16,3 ± 0,5 (+7 %) | 16,3 ± 2,1 (+7 %) |
| `battery-n800` | 22,3 ± 7,1 | 20,3 ± 6,2 (−9 %) | 22,7 ± 9,1 (+2 %) | 32,3 ± 1,7 (**+45 %**) |
| `battery-n1000` | 46,3 ± 0,9 | 44,7 ± 3,4 (−4 %) | 46,7 ± 1,2 (+1 %) | 42,3 ± 4,5 (−9 %) |
| `battery-sparse-n250` | 4,0 ± 1,4 | 3,3 ± 0,5 (−17 %) | 3,7 ± 0,5 (−8 %) | 4,7 ± 0,5 (+17 %) |
| `battery-sparse-n500` | 4,3 ± 1,7 | 5,0 ± 2,2 (+15 %) | 5,7 ± 1,7 (+31 %) | 6,0 ± 1,6 (+38 %) |
| `area-26-n157` | 4,7 ± 0,5 | 4,7 ± 0,5 (+0 %) | 4,7 ± 0,5 (+0 %) | 4,7 ± 0,5 (+0 %) |
| `area-27-n72` | 4,0 ± 0,8 | **0,0 ± 0,0 (−100 %)** | 2,3 ± 1,9 (−42 %) | 1,0 ± 0,0 (−75 %) |
| `area-29-n43` | 1,3 ± 0,5 | 1,0 ± 0,0 (−25 %) | 2,0 ± 0,0 (+50 %) | 1,0 ± 0,0 (−25 %) |
| **`reference-n1607`** | **34,7 ± 5,2** | **34,3 ± 5,4 (−1,0 %)** | **34,3 ± 4,7 (−1,0 %)** | **34,3 ± 5,4 (−1,0 %)** |

En la instancia del criterio las tres celdas dan **−1,0 %** contra un umbral de −30 %, y ese −1,0 %
(34,7 → 34,3, o sea **un solo cruce sobre la media de tres semillas**) está **por debajo del piso
de ruido de §7.2**, donde re-correr el control ya movía los cruces en ±1. No es un efecto pequeño:
es indistinguible de no hacer nada. La σ de la propia celda (±5,2) es cinco veces el efecto.

### 7.5 Las demás métricas en las instancias del criterio

`reference-n1607`:

| celda | travel | `k` | `balance` | `balance_excl_min` | degeneradas | `dur_min` | `dur_median` | `dur_max` | exención ociosa |
| --- | --- | :-: | :-: | :-: | :-: | ---: | ---: | ---: | :-: |
| `control` | 58 988 ± 1 213 | 25,0 | 0,839 | 0,850 | 0 | 9 018 | 10 184 | 10 743 | — |
| `exempt-lower` | 58 868 (−0,2 %) | 25,0 | 0,838 | 0,846 | 0 | 9 016 | 10 184 | 10 762 | **3/3** |
| `exempt-upper` | 58 956 (−0,1 %) | 25,0 | 0,839 | 0,849 | 0 | 9 018 | 10 184 | 10 752 | **3/3** |
| `exempt-both` | 58 792 (−0,3 %) | 25,0 | 0,838 | 0,846 | 0 | 9 016 | 10 184 | 10 762 | **6/6** |
| `exempt-lower-last` | 58 824 (−0,3 %) | 25,0 | 0,836 | 0,840 | 0 | 8 996 | 10 184 | 10 762 | 0/3 |

`relleno_msf` en las tres áreas:

| instancia | `control` | `exempt-lower` | `exempt-upper` | `exempt-both` |
| --- | ---: | ---: | ---: | ---: |
| `area-26-n157` | 1 233 ± 278 | 1 233 (**+0,0 %**) | 1 233 (**+0,0 %**) | 1 233 (**+0,0 %**) |
| `area-27-n72` | 1 580 ± 212 | 409 (−74,1 %) | 525 (−66,8 %) | 153 (−90,3 %) |
| `area-29-n43` | 244 ± 29 | 167 (−31,5 %) | 257 (+5,3 %) | 167 (−31,5 %) |

`area-26` es **exactamente cero** en las tres celdas y las tres semillas — no "casi cero": las
filas son idénticas al control byte a byte, porque su `dur_min` medio (7 283 s) está sobre el piso
—solo la semilla 2 cae debajo, a 6 974 s, y aun así la exención queda ociosa— y las exenciones
quedan ociosas 3/3.

Agregado sobre las 12 instancias (suma de relleno, de auto-cruces de calle y de travel; media y
mínimo de balance):

| celda | Σ relleno | Σ `crossings_road` | Σ travel | balance medio | balance mínimo | degeneradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `control` | 74 286 | 153,7 | 179 112 | **0,888** | **0,828** | **0** |
| `exempt-lower` | **71 657** | **144,7** | **176 344** | 0,753 | **0,014** | **1** |
| `exempt-upper` | 73 372 | 154,3 | 179 311 | 0,886 | 0,808 | 0 |
| `exempt-both` | 75 287 | 158,7 | 180 836 | 0,820 | 0,564 | 0 |

### 7.6 Veredicto por celda — TODAS fallan el criterio

| celda | cláusula que falla | detalle |
| --- | --- | --- |
| **`exempt-lower`** | cruces n1607, relleno `area-26`, balance, degeneradas | −1,0 % de cruces; `area-26` +0,0 %; **balance 0,014** en `battery-n50`; **1 ruta degenerada** (3/3 semillas) |
| **`exempt-upper`** | cruces n1607, relleno áreas, cruces `area-29` | −1,0 %; `area-26` +0,0 % y `area-29` **+5,3 %**; cruces `area-29` 1,3 → 2,0 |
| **`exempt-both`** | cruces n1607, relleno `area-26`, balance | −1,0 %; `area-26` +0,0 %; **balance 0,564** en `battery-sparse-n500` |
| **`exempt-lower-last`** | cruces n1607, relleno y cruces `area-26`, balance | +0,0 %; `area-26` −16,6 % y cruces 4,7 → 5,0; **balance 0,576** en `battery-n1000` |
| `exempt-none` (instrumento) | — | no es candidata: es el control por construcción |

Ninguna celda cumple. `drops` = 0 y `k` ≤ 26 se cumplen en todas, pero una celda que cumple parte
del criterio y falla otra parte **falla el criterio**.

**Sobre las dos lecturas del balance.** `exempt-lower` pasa de 0,014 a **1,000** en `battery-n50`,
de 0,376 a **1,000** en `area-27` y de 0,552 a **0,880** en `sparse-n250` si se excluye la ruta más
corta. Con la lectura excluyente, su única falla de balance desaparecería. **El criterio se juzga
con la lectura no excluyente**, declarada así en el pre-registro §2.4 antes de medir, y la celda
falla. Cambiar de lectura ahora sería elegir la regla después de ver el resultado: precisamente lo
que el brazo histórico hacía y lo que este ciclo se comprometió a no heredar. Se publican las dos y
se juzga con la conservadora.

**Sobre `exempt-lower` como la celda "más cerca".** Es la única que mejora los tres agregados a la
vez (relleno −3,5 %, cruces −5,9 %, travel −1,5 %). No es una ganadora parcial: es una ganadora que
falla el criterio. Lo que compra lo compra en **tres de las cuatro instancias de piso activo**
(`battery-n50` −83,0 %, `area-27` −74,1 %, `area-29` −31,5 % de relleno); en la cuarta,
`sparse-n250`, el relleno **empeora** +4,4 %. Y lo paga con una ruta de **120 s** en `battery-n50`
(contra `dur_max` 8 295 s en la misma solución), que es exactamente la ruta-stub que la compuerta
de degeneración existe para vetar.

### 7.7 Cuadro de predicciones

| # | predicción del §3 | resultado | veredicto |
| --- | --- | --- | --- |
| 1 | C1: `exempt-none` reproduce `control` al segundo, 9/9 | 7/9 exactas; las 2 restantes ≤ 0,17 % contra un piso de ruido de 0,92 % del propio control | **pasa, con la salvedad medida** |
| 2 | C2: el vehículo del último índice queda inactivo y explica el nulo histórico | **activo 12/12**; la explicación candidata queda **refutada** | **falsada** |
| 3 | `exempt-upper` deja `k` igual o menor y baja cruces; `exempt-lower` baja relleno sin subir `k` | en n1607 `k` = 25 en las tres celdas y los cruces se mueven −1 % (dentro del ruido); el relleno de áreas baja solo donde el piso ya cobraba | **falsada en el régimen del criterio** |
| 4 | riesgo: `exempt-upper` degenera en una ruta gigante (travel > +3 % o balance < 0,60) | **no ocurrió**: travel −0,1 %, balance 0,839, 0 degeneradas en n1607. El riesgo se materializó en la celda **contraria**: `exempt-lower` produjo la ruta de 120 s | **no se materializó (en esa celda)** |
| 5 | resultado más probable: plano o negativo | plano en el régimen operativo, negativo bajo el criterio | **acertada** |

---

## 8. Veredicto

**La flota asimétrica NO cumple el criterio de aceptación en ninguna de sus cuatro celdas. No se
cambia ningún default de producción: el brazo `actual` queda intacto y las exenciones quedan como
brazos opt-in del driver de barrido.**

En `reference-n1607` las tres celdas dan **−1,0 % de auto-cruces de calle** contra un umbral de
−30 %, y ese −1,0 % **está por debajo del ruido de re-ejecución del propio control** (hasta 0,92 %
de travel y ±1 cruce, §7.2). En las áreas, `area-26` es **exactamente +0,0 %** en las tres celdas.
Y donde alguna celda sí mueve la aguja, lo paga con balance: 0,014 en `battery-n50` para
`exempt-lower`, 0,564 en `sparse-n500` para `exempt-both`.

**Por qué, con los números del propio ciclo.** El régimen operativo no tiene margen para ninguno de
los dos sumideros:

- **El sumidero del piso no tiene déficit que absorber.** En `reference-n1607` la ruta más corta del
  control dura **9 018 s**, muy por encima de `T_min` = 7 200. El piso no está cobrando, así que
  perdonárselo a un vehículo no libera nada — y el solver lo confirma dejando ese vehículo vacío en
  **3 de 3** semillas. La correspondencia se sostiene en **31 de las 36** filas (§7.3): piso activo
  ⟹ sumidero usado en las 12 filas de ese régimen; piso inactivo ⟹ sumidero ocioso en 21 de 24.
- **El sumidero del techo choca contra la capacidad dura.** La ruta más larga del control dura
  **10 743 s** en media (máximo por semilla 10 766 s) contra `T_max` = **10 800 s**, que la dimensión `Time` impone como capacidad dura y
  que ninguna exención del techo **blando** toca. La ruta eximida tiene ~57 s de holgura antes del
  muro. El sumidero existe y su capacidad es prácticamente cero.

Las rutas de `reference-n1607` viven **entre el punto medio y `T_max`**, es decir en el tramo donde
el precio marginal es +501/s y el binding es la capacidad dura, no las cotas blandas. Eximir de una
cota blanda a un vehículo es, en ese régimen, una operación sobre un término que no está activo.

**Sobre el mecanismo del §1.** La descomposición aritmética del objetivo es correcta —el subsidio
44:1 a partir rutas existe y está bien calculado— y **otra vez** no predijo el comportamiento del
solver, igual que le pasó al predicado de régimen del ciclo anterior. La aritmética dice qué es
barato para el modelo; no dice si la restricción está activa en el punto donde el modelo opera. En
`reference-n1607` no lo está. Se registra como el segundo fallo consecutivo de una predicción
derivada de esta misma estructura de precios.

### Lo que sí queda establecido

1. **El nulo de `exempt-last` no se debía a un vehículo inactivo.** El último índice está **activo
   en 12 de 12 filas** medidas. La hipótesis que este ciclo debía confirmar o descartar queda
   **descartada con dato**. El nulo se debe a que en las instancias grandes el piso no cobra, no a
   dónde apuntaba la exención.
2. **`exempt-lower` = `exempt-last` re-medido con el criterio de hoy sigue fallando, pero por otra
   cláusula.** El descarte histórico se apoyaba en balance ≥ 0,80 y en la métrica de cuerdas, ambos
   obsoletos. Re-medido con balance ≥ 0,60, `crossings_road` y semillas reales, **falla igual**:
   por relleno de `area-26` (+0,0 %), por balance (0,014) y por una ruta degenerada. La reapertura
   estaba justificada y el resultado es el mismo por razones distintas — que es información nueva,
   no una confirmación del razonamiento viejo.
3. **Un predicado que sí correlaciona con el uso del sumidero.** "¿La ruta más corta del control
   cae bajo `T_min`?" acierta si el solver usará la exención del piso en **31 de 36** filas — 10 de
   12 instancias limpias, 2 mezcladas (§7.3). No es un predicado de qué configuración gana —eso ya
   se falsó— sino de si una palanca concreta tiene de dónde agarrar, y no es determinista: hay
   filas ociosas con el piso cobrando y filas usadas con el piso inerte. Se publica como
   observación verificada, no como regla adoptada: `dur_min` del control es **post-solver**, así
   que su versión utilizable de verdad habría que construirla y validarla en su propio ciclo.
4. **El piso de ruido de `reference-n1607` es ≈1 % de travel y ±1 auto-cruce**, medido re-corriendo
   el control contra sí mismo con las mismas semillas. Cualquier ciclo futuro que reporte efectos
   de esa magnitud en esta instancia está reportando ruido. La causa es que el GLS se corta por
   reloj de pared y no por iteraciones.

### Lo que queda descartado

- **La flota asimétrica como palanca de geometría en el régimen operativo**: falsada. Las cuatro
  celdas fallan el criterio y el efecto en `n1607` no supera el ruido de re-ejecución. No reabrir
  sin dato nuevo.
- **"La exención cayó en un vehículo inactivo" como explicación del nulo de `exempt-last`**:
  refutada, 12/12 filas con el vehículo activo.
- **Eximir del techo blando como forma de aliviar rutas saturadas**: no funciona mientras `T_max`
  siga siendo capacidad dura a ~57 s de la ruta más larga. Lo que ata a esas rutas es la capacidad
  dura, no el techo blando. Un ciclo que quiera atacar eso tiene que mover `T_max`, que es una
  decisión de producto (jornada del censista), no de solver.

Queda **abierto**, sin estatus de propuesta: en tres de las cuatro instancias de piso activo la
exención del piso produce caídas grandes de relleno (−83 % en `battery-n50`, −74 % en `area-27`,
−32 % en `area-29`; en `sparse-n250` sube +4,4 %) al precio de una ruta residual corta. Si alguna vez el objetivo admitiera explícitamente una ruta parcial —
una decisión operativa, no de configuración— esa sería la celda a re-examinar, con su propio
pre-registro y con la compuerta de degeneración redefinida **antes** de medir, no después.
