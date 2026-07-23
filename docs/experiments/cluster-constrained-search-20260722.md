# Restringir el espacio factible: clusters blandos y arranque en caliente

**Fecha:** 2026-07-22
**Estado al commitear esta sección:** pre-registro. Diseño, brazos, instancias, métricas,
criterio y la aritmética de la Fase 0 —con sus predicciones— se commitean **antes** de
medir nada. Los resultados se agregan después, sin tocar el criterio.

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual,
coeficiente de span espacial 3) intactos. Lo nuevo es opt-in y, sin las banderas, el
pipeline recorre exactamente el mismo camino de código de siempre.

---

## Por qué este ciclo

Diez ciclos, ninguna ganadora verificada, ningún default cambiado. Lo cerrado con mecanismo
identificado:

| Familia | Cómo se cerró |
| --- | --- |
| Pisos de duración, de paradas y combinados | tres flancos independientes (relleno, varianza, umbral×fuerza) |
| Recalibrar penalizaciones del objetivo | no existe configuración única sin guard por régimen |
| Costo de arco convexo | los cruces no son arcos largos (refutado dos veces) |
| Post-pass de re-secuenciado 2-opt | empeora cruces en 12 de 12 sobre base limpia |
| Multi-arranque | empate a todo N; a 120 s la GLS ya está en meseta |
| El instrumento de medición | convergió (mover el cero de `MSF_k` a `UB_k` cambia 0 de 12 veredictos) |

El último fallo vivo está diagnosticado y es estructural. La ruta degenerada de
`feasible-floor-b095` tiene **3 paradas y 10 485 s de duración contra un `T_max` de
10 800 s**: el 97 % de su capacidad dura. Son tres árboles aislados a ~2,8 h del resto, y
las otras 24 rutas llevan 53–78 paradas cerca de su propio techo. Ninguna penalización la
arregla porque el movimiento que incentiva —añadir paradas— es **infactible**.

De ahí la lectura que este ciclo prueba, y que es lo único de la lista que no se ha tocado:

> La palanca no está en cómo se **precian** las soluciones ni en cómo se **buscan**, sino
> en qué soluciones están **disponibles**.

---

## Los dos brazos

### Brazo A (principal) — clusters blandos

kmeans sobre las coordenadas proyectadas con `k = choose_k(...)` —el mismo estimador de
flota que ya usa `cluster_first`— asigna cada árbol a un cluster. Cada cluster posee un
bloque fijo de vehículos y cada nodo queda habilitado **sólo** en los vehículos de su
cluster y de sus `r` clusters vecinos más cercanos por centroide.

Esto restringe el **espacio factible**, no el objetivo. Es distinto de `cluster_first`
—estrategia ya refutada, que no se reimplementa aquí— en un punto que es justamente la
hipótesis: `cluster_first` resuelve un VRP independiente por cluster y no puede rebalancear
nunca los bordes; esto mantiene **una sola pasada global** que sí puede.

Implementación: se restringe el dominio de `VehicleVar` de cada nodo. `-1` permanece en el
dominio, así que la disyunción de *drop* sigue viva y una restricción mal dimensionada se
manifiesta como **drops medibles** en vez de como un modelo infactible que devuelve `None`.
(`SetAllowedVehiclesForIndex` sería la API natural, pero el binding Python de OR-Tools
9.15.6755 no convierte su `absl::Span<int const>`; está verificado, no supuesto.)

**Relación vehículos↔clusters, declarada porque es un riesgo del diseño.** El estimador
`estimate_max_vehicles` devuelve una cota superior con buffer de 5, siempre mayor que
`choose_k`. Cada cluster recibe `m = ceil(max_vehicles / K)` vehículos —el mismo número
para todos, para que ningún cluster quede desabastecido por el orden arbitrario de un
reparto round-robin—, de modo que la flota total del modelo pasa a ser `K · m`. En
`reference-n1607` eso es 24 × 2 = **48 vehículos** contra los 36 del estimador. Los
vehículos no usados no cuestan nada (medido en `objective-audit-20260718`), pero el cambio
queda registrado en las columnas `cluster_count` y `vehicles_per_cluster` del CSV.

Grilla de `r`: **{0, 1, 2}**. `r = 0` no está para ganar sino para **acotar el efecto**: es
el extremo de partición dura, y sin él no se puede saber si un eventual resultado de
`r = 1` viene de la coherencia espacial o de la holgura que dejan los vecinos. `r = 2` es el
otro extremo útil: con `K = 24` en `n=1607`, tres clusters de 24 ya son un octavo del
territorio, y más vecinos degeneran hacia el modelo sin restricción.

### Brazo B (secundario) — arranque en caliente

Sembrar la GLS con la solución de `greedy` o de `cluster_first`
(`ReadAssignmentFromRoutes` + `SolveFromAssignmentWithParameters`) en vez de dejar que
`PATH_CHEAPEST_ARC` construya desde cero. Hipótesis: una semilla espacialmente coherente
ancla la geometría.

Una semilla que no sea una asignación factible **aborta la corrida con error**; no hay
caída silenciosa a arranque en frío. Si el arranque en caliente no se puede leer, eso es un
resultado, no un caso a manejar.

---

## Fase 0 — aritmética antes de medir

Aritmética pura sobre las 12 instancias congeladas, sin solver. `K = choose_k`,
`max_veh` = estimador con buffer, `m = ceil(max_veh/K)`.

| Instancia | n | `nn` (s) | K | max_veh | m | veh. total | tam. cluster mín–máx | carga peor cluster (`r=0`) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `battery-n50` | 50 | 42.2 | 1 | 7 | 7 | 7 | 50–50 | 0.107 |
| `battery-n100` | 100 | 25.1 | 2 | 8 | 4 | 8 | 39–61 | 0.205 |
| `battery-n200` | 200 | 17.7 | 3 | 9 | 3 | 9 | 59–80 | 0.340 |
| `battery-n400` | 400 | 14.0 | 6 | 13 | 3 | 18 | 8–124 | 0.513 |
| `battery-n800` | 800 | 11.4 | 12 | 20 | 2 | 24 | 30–115 | 0.699 |
| `battery-n1000` | 1 000 | 11.1 | 15 | 24 | 2 | 30 | 36–124 | 0.753 |
| `battery-sparse-n250` | 250 | 34.3 | 4 | 11 | 3 | 12 | 32–101 | 0.481 |
| `battery-sparse-n500` | 500 | 19.2 | 8 | 15 | 2 | 16 | 19–132 | **0.851** |
| `area-26-n157` | 157 | 15.5 | 2 | 8 | 4 | 8 | 55–102 | 0.320 |
| `area-27-n72` | 72 | 7.6 | 1 | 7 | 7 | 7 | 72–72 | 0.122 |
| `area-29-n43` | 43 | 9.2 | 1 | 6 | 6 | 6 | 43–43 | 0.086 |
| `reference-n1607` | 1 607 | 17.1 | 24 | 36 | 2 | 48 | **1**–142 | **0.901** |

`carga peor cluster` = `tam · (servicio + nn) / (m · T_max)`: la fracción de la capacidad
dura de un cluster que consume su propio trabajo bajo `r = 0`, con travel valuado al
vecino más cercano.

### Corrección del optimismo de `nn`, y la primera predicción

`nn` **subestima** el travel real: es la cota de vecino más cercano, que viola la
restricción de grado 2 de un camino. Contra la propia corrida de control de `n=1607`
(travel ≈ 60 909 s repartidos en 1 582 arcos) el travel real por arco es **≈38.5 s, unas
2.25× `nn`**. Reescalando la última columna con ese factor:

| Instancia | carga con `nn` | carga con travel realista |
| --- | ---: | ---: |
| `reference-n1607` | 0.901 | **1.042** |
| `battery-sparse-n500` | 0.851 | **0.998** |
| `battery-n1000` | 0.753 | 0.833 |
| `battery-n800` | 0.699 | 0.774 |
| resto | ≤0.513 | ≤0.581 |

**Predicción 1, registrada antes de medir: `cluster-r0` produce drops en
`reference-n1607`.** El cluster más grande tiene 142 árboles y sólo 2 vehículos:
`142 × 120 + 141 × 38.5 = 22 469 s` contra una capacidad de `2 × 10 800 = 21 600 s`. Es
infactible por ~4 %, y la disyunción convertirá esa infactibilidad en nodos abandonados.
`battery-sparse-n500` queda justo en el filo (0.998) y puede caer de cualquier lado. En el
resto de la batería hay holgura y no debería haber drops.

Éste es el riesgo que el ciclo tiene que **reportar, no ablandar**: si `r = 0` da drops, se
publica que da drops. No se re-dimensionan los clusters ni se sube `m` hasta que funcione.

### La segunda predicción: `reference-n1607` siempre tiene un cluster de un solo árbol

kmeans sobre `reference-n1607` produce, en las tres semillas probadas y de forma estable,
**exactamente un cluster de tamaño 1**:

```
seed=0  K=24  sizes=[1, 26, 30, 40, 44, 44, 46, 48, 51, 51, 51, 56, 58, 59, 61, 83, 83, 86, 88, 102, 104, 120, 133, 142]
seed=1  K=24  sizes=[1, 19, 28, 30, 36, 38, 40, 44, 46, 50, 61, 62, 66, 69, 71, 73, 81, 86, 95, 98, 121, 121, 131, 140]
seed=2  K=24  sizes=[1, 25, 30, 37, 40, 47, 48, 48, 54, 60, 66, 67, 73, 75, 75, 79, 85, 86, 88, 88, 95, 108, 109, 123]
```

Es el mismo aislamiento geográfico que produjo la ruta degenerada de `b095`: el territorio
tiene un extremo a ~2,8 h del resto y kmeans lo separa siempre.

**Predicción 2: `cluster-r0` produce una ruta degenerada en `reference-n1607` en las 5
réplicas, por construcción.** Bajo `r = 0` ese árbol no puede compartir vehículo con nadie,
así que su ruta tiene exactamente 1 parada. `cluster-r0` **empeoraría** el control `actual`,
que mide 0.0±0.0 degeneradas. Con `r ≥ 1` el singleton puede fundirse con su cluster vecino
y la predicción no aplica.

Esto es informativo aunque salga mal: significaría que una partición previa por geometría
**crea** exactamente la patología que la serie lleva tres ciclos intentando matar, y que el
aislamiento de esos árboles no es un artefacto del solver sino del territorio.

### La tercera predicción: los cruces probablemente no bajan un 30 %

La métrica `crossings` del barrido es la suma de **auto-cruces por ruta** (secuencia de
paradas que se cruza consigo misma), no el solape entre rutas. Los clusters blandos
restringen a qué vehículo va cada nodo, que es un mecanismo de **solape inter-ruta**
(`worst_iou`, `interleave_per_route`), no de auto-cruce.

Y el mecanismo del auto-cruce ya está identificado desde `route-disorder-20260714`: bajo el
piso `T_min` del brazo `actual`, las rutas **rellenan** —caminan de más para alcanzar el
piso— y ese relleno es lo que se enrosca. Confinar una ruta a un cluster compacto no quita
el piso, así que el incentivo a rellenar sigue intacto.

**Predicción 3: los brazos `cluster-r{0,1,2}` sobre `actual` mejoran `worst_iou` e
`interleave_per_route` de forma real, pero NO alcanzan el −30 % de `crossings`.** Si la
predicción se cumple, el ciclo habrá localizado el efecto de la restricción en la métrica
correcta y habrá mostrado que en `actual` los cruces están tarifados, no asignados.

Por eso mismo se pre-registra un cuarto brazo, `cluster-r1-no-floor`: es la única
combinación en la que la predicción 3 no bloquea el criterio, porque `no-floor` ya elimina
el incentivo a rellenar (y a cambio deja rutas *stub*, que es lo que la coherencia espacial
podría estar en posición de arreglar). No se añade después de ver resultados: se añade aquí,
por la aritmética de arriba.

### La tensión del Brazo B, resuelta antes de medir

`multistart-sweep-20260721` midió que a `T = 120 s` la GLS **ya está en meseta**: cinco
órdenes de nodos distintos —que cambian por completo la construcción de
`PATH_CHEAPEST_ARC`— convergen a travel indistinguible del ruido entre réplicas
(62 088±1 738 con N=1 contra 61 209±1 167 con N=5, empate). Eso es evidencia previa de que
el punto de partida **se lava**.

No es idéntico a este caso: aquello perturbaba el orden de nodos de la **misma** heurística
de construcción, mientras que esto siembra una solución **estructuralmente distinta**. Las
dos lecturas posibles son:

1. **Se lava.** La GLS pasa 120 s reparando; su trayectoria está dominada por las
   penalizaciones guiadas, no por el punto inicial, y ambos arranques terminan en la misma
   meseta.
2. **Ancla.** A `n = 1607` el límite de 120 s está *topado* (`min(30 + 1.5n, 120)`), así que
   la corrida está mucho menos convergida en términos relativos que a `n = 50`, y una
   semilla estructuralmente mejor puede sobrevivir hasta el final.

**Predicción 4, la que este ciclo se juega: se lava, incluso en `n = 1607`.** El argumento
en contra de la lectura 2 es que el ciclo de multi-arranque ya midió `n = 1607`
específicamente y ahí también empató; y el argumento adicional es que la semilla `greedy`
es *peor* que la de `PATH_CHEAPEST_ARC` en objetivo, así que la primera fase de mejora de la
GLS la borra. Se espera **empate en las 12 instancias** para `warm-greedy` y para
`warm-cluster`.

Si sale inerte, era predecible y queda predicho aquí. El falsador está igual de escrito: si
`warm-cluster` difiere de `actual` de forma **real** bajo la regla de varianza en
`reference-n1607`, la lectura de meseta del ciclo anterior era demasiado general y hay que
matizarla.

---

## Diseño

Estrategia `spatial_term`, **12 instancias congeladas**, **5 réplicas reales** (semillas
1–5, permutación del orden de nodos; OR-Tools no expone RNG, verificado). Driver
`config_algorithm_sweep`. Un CSV y un flujo por brazo.

| # | Brazo | Celda | Base | Papel |
| --- | --- | --- | --- | --- |
| 1 | `actual` | — | `actual` | Control de producción. **Re-corrido en este ciclo.** |
| 2 | `cluster-r0` | `--only-cell cluster-r0` | `actual` | Partición dura: acota el efecto por arriba. |
| 3 | **`cluster-r1`** | `--only-cell cluster-r1` | `actual` | **El brazo central.** |
| 4 | `cluster-r2` | `--only-cell cluster-r2` | `actual` | Vecindario ancho: acota el efecto por abajo. |
| 5 | `cluster-r1-no-floor` | `--only-cell cluster-r1-no-floor` | `no-floor` | Coherencia espacial sin incentivo a rellenar. |
| 6 | `warm-greedy` | `--only-cell warm-greedy` | `actual` | Semilla barata y determinista. |
| 7 | `warm-cluster` | `--only-cell warm-cluster` | `actual` | Semilla espacialmente coherente. |

7 brazos × 12 instancias × 5 semillas = **420 filas**.

`actual` se **re-corre** en vez de releerse de reportes anteriores. Está medido que la
varianza **entre corridas** supera la varianza entre semillas **dentro** de una corrida: el
travel de una misma configuración se movió de 59 971 a 62 751 s entre dos ciclos, un salto
mayor que su propia desviación entre semillas. Comparar contra medias publicadas en otros
reportes no está justificado.

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s |
| T_max | 10 800 s |
| T_min | 7 200 s |
| Límite de tiempo del solver | `min(30 + 1.5·n, 120)` s |
| Semillas | 1–5 |

Instancias: batería `{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales
`{157, 72, 43}` y `n=1607`. Cargadas con `load_instances`.

### Nota de ejecución

Los siete flujos corren **en paralelo** sobre la misma máquina. El límite de tiempo del
solver es de reloj, así que la contención de CPU reduce iteraciones de GLS:
`wall_clock_sec` y los tiempos de fase **no se usan para juzgar nada**, ni contra barridos
previos ni entre brazos. Los siete corren bajo el mismo esquema, así que la comparación de
métricas de calidad entre ellos sí es interna y homogénea.

Coste declarado del brazo `warm-cluster`: su semilla es una corrida completa de
`cluster_first`, así que gasta aproximadamente el doble de cómputo que los demás. Es una
magnitud estructural, no medida por reloj.

---

## Criterio de aceptación (heredado, NO renegociable a posteriori)

- **`reference-n1607`:** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** `relleno_msf_sec` **−≥30 %** vs `actual`; cruces **sin
  empeorar**.
- **Global:** **0 drops**; **balance min/max ≥0.60** en **toda** instancia; **0 rutas
  degeneradas**, con la definición absoluta de siempre (**<5 paradas** O **<1 800 s**).

Se juzga con **`relleno_msf`** (cero demostrado y conservador). El PR que agrega
`relleno_ub` como columna de contexto sigue abierto al empezar este ciclo, así que no se
publica esa columna.

### Regla de varianza

Una diferencia entre brazos cuenta como **real** sólo si

```
|media_A − media_B| > desv_A + desv_B
```

sobre las 5 semillas. Si no la supera se reporta como **empate**, con esa palabra. Un brazo
con 0 fallos contra 0.2±0.4 es un **empate**, no una victoria.

### Sobre qué se evalúa

Los criterios se evalúan sobre la **media** de las 5 réplicas. Balance y rutas degeneradas
se reportan **además** por peor réplica, porque los fallos vivos de la serie son de cola.

**Si un brazo pasa el criterio COMPLETO es la primera ganadora verificada de la serie, y se
dice con esas palabras. Si no, no.**

---

## Compromisos de reporte

1. Este pre-registro se **commitea antes de medir**, como los seis anteriores de la serie.
2. El criterio **no se toca** una vez leídos los resultados.
3. **Si el resultado es negativo se reporta igual de fuerte que uno positivo.**
4. Las cuatro predicciones de la Fase 0 quedan fijadas arriba para poder ser **refutadas**,
   no racionalizadas después.
5. Los drops de `cluster-r0`, si aparecen, se publican como resultado del brazo. No se
   re-dimensionan los clusters para hacerlos desaparecer.

---

## Reproducción

```bash
# Cargar la suite congelada (UUID deterministas, la cache de OSRM acierta)
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py load_instances

for cell in actual cluster-r0 cluster-r1 cluster-r2 cluster-r1-no-floor \
            warm-greedy warm-cluster; do
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv "docs/experiments/cluster-constrained-search-20260722-$cell.csv" \
      --only-cell "$cell" --seeds 1 2 3 4 5 &
done
wait
```

La aritmética de la Fase 0 se reproduce sin solver con `build_cluster_plan` sobre las
instancias congeladas; `choose_k`, `estimate_max_vehicles` y `kmeans` son deterministas
dada la semilla.

---

---

## Resultados

Datos: `cluster-constrained-search-20260722-{actual,cluster-r0,cluster-r1,cluster-r2,
cluster-r1-no-floor,warm-greedy,warm-cluster}.csv`. **420 filas**: 7 brazos × 12 instancias
× 5 semillas. Un CSV y un flujo por brazo, mismo grado de paralelismo para los siete.

### Nota de ejecución añadida por un fallo de integración (declarada)

El brazo `warm-greedy` abortó en la primera corrida sobre `battery-n400` con
`warm start routes are not a feasible assignment`. Diagnóstico antes de tocar nada: **defecto
de integración propio, no propiedad del problema.** `solve_greedy` empaqueta contra `T_max`
usando `ceil(Σ arcos)`, mientras que la dimensión `Time` del modelo suma `ceil(arco +
servicio)` **por arco**; sumar redondeos hacia arriba sobrepasa `T_max` hasta en ~1 s por
arco, y en rutas de 72–77 paradas eso son +17 a +24 s. La semilla se construía inválida
bajo el modelo que siembra. Se corrigió construyendo la semilla con la misma aritmética de
la dimensión `Time` (`split_to_solver_capacity`), **sin tocar `T_max` ni relajar ninguna
restricción**, y se **re-corrió el brazo completo** (no se reanudó desde las filas ya
escritas: la clave de reanudación no codifica la versión del constructor). El aborto ruidoso
pre-registrado es lo que expuso el defecto y se mantiene. Los otros seis brazos no usan
`warm-greedy` y no se tocaron.

### El resultado en una línea

**Restringir el espacio factible no produce una ganadora: los clusters blandos rompen la
factibilidad —kmeans ignora la capacidad y el modelo abandona árboles— y disparan los
cruces; el arranque en caliente no se lava sino que ancla a una geometría peor.** Los siete
brazos fallan el criterio. **No hay ganadora verificada, y no se dice esa frase.**

### Las cuatro predicciones de la Fase 0, contra lo medido

| # | Predicción pre-registrada | Resultado | Veredicto |
| --- | --- | --- | --- |
| 1 | `cluster-r0` produce drops en `reference-n1607` | drops por semilla `[39,17,0,72,15]`; y además en `battery-n{200,400,800,1000}` | **acertada** (y el alcance fue mayor) |
| 2 | `cluster-r0` degenera en `n=1607` en 5/5 réplicas | `[2,2,1,1,2]` rutas degeneradas: 5/5 con ≥1 | **acertada** |
| 3 | los brazos cluster sobre `actual` NO alcanzan −30 % de cruces | cruces **+589 %/+162 %/+89 %** (dirección contraria) | **acertada** (con dirección más extrema) |
| 4 | el arranque en caliente **se lava** (empate) en las 12 instancias | `warm-greedy` y `warm-cluster` difieren de `actual` de forma **real** en `n=1607` | **REFUTADA** |

Tres de cuatro predicciones acertaron; la cuarta se refutó, y su refutación es el hallazgo
más informativo del ciclo (§ Brazo B).

### Brazo A — clusters blandos

`reference-n1607`, media ± desviación sobre 5 réplicas. Control `actual` re-corrido:
cruces 68.2±6.0, travel 60 941±957, k 25.0±0.0, `worst_iou` 0.447±0.046,
`interleave_per_route` 125.2±30.1.

| Brazo | drops (filas/5, total) | k | cruces | Δ cruces | travel | Δ travel | `worst_iou` | `interleave` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cluster-r0` | 5/5, 143 | 35.4±1.4 | 470±86 | +590 % (real) | 77 737±2 361 | +27.6 % (real) | 0.552 (+23 %, real) | 20.0 (−84 %, real) |
| `cluster-r1` | 3/5, 100 | 30.6±1.0 | 179±60 | +162 % (real) | 69 512±2 949 | +14.1 % (real) | 0.604 (+35 %, real) | 48.8 (−61 %, real) |
| `cluster-r2` | 3/5, 41 | 28.6±1.2 | 129±34 | +89 % (real) | 68 413±6 196 | +12.3 % (real) | 0.621 (+39 %, real) | 60.4 (−52 %, real) |

**Los drops invalidan la comparación en sí misma.** Con la disyunción viva, la restricción mal
dimensionada —predicha en la Fase 0— se cobra en árboles abandonados: cuando un cluster no
cabe en sus `m` vehículos, el solver prefiere pagar el `DROP_PENALTY` antes que violar
`T_max`. El travel y los cruces de arriba son de soluciones que **no visitan todos los
árboles**, así que ni siquiera son comparables con `actual` en el mismo problema. Aflojar
`r` reduce los drops (302 → 131 → 41 nodos totales) pero no los elimina, porque el cluster
de 142 árboles de `n=1607` (Fase 0) sigue sin caber en 2 vehículos aunque le sumemos los
vecinos.

**Y donde no hay drops, el efecto sobre los cruces es el contrario al buscado.** Confinar
cada nodo a un subconjunto de vehículos le quita al solver la libertad de asignar el
vehículo geográficamente natural, así que las rutas zigzaguean **más**: los auto-cruces
suben +89 % a +590 %. El único movimiento en la dirección esperada es `interleave_per_route`
(−52 % a −84 %, real): las rutas se entrelazan menos entre sí, exactamente el mecanismo
inter-ruta que la Predicción 3 anticipó. Pero `worst_iou` **empeora** (+23 % a +39 %): las
cajas contenedoras se solapan más, no menos. El brazo compra un tipo de coherencia
(menos entrelazado) pagándolo con dos incoherencias peores (más auto-cruce, más solape de
bbox) y con árboles abandonados.

En las **áreas chicas** los brazos cluster son **inertes** (`K` = 1–2, `m` = 4–7, ninguna
ruta cerca del techo de vehículos): `relleno_msf` y cruces idénticos a `actual` hasta el
segundo. La restricción sólo binda donde `k` es grande, y ahí rompe la factibilidad.

#### `cluster-r1-no-floor` — el espejismo del ciclo

Sobre el papel es el mejor brazo: en `n=1607` cruces **−53.7 %**, travel **−17.6 %**, y en
las áreas relleno **−42 % / −96 % / −83 %**, todos superando el umbral. **Es un artefacto de
los drops.** El brazo abandona 100 árboles (semillas `[20,0,1,0,79]` en `n=1607`): rutear
menos árboles baja el travel y los cruces por construcción. Su balance mínimo es **0.011**
—28 filas bajo 0.60— y degenera en **2.6±0.8** rutas por réplica, el peor de los siete.
Falla `0 drops`, falla balance y falla rutas degeneradas. Los números bonitos son el precio
de no hacer el trabajo. **Es el ejemplo exacto de por qué el criterio incluye `0 drops`
antes que cualquier métrica de calidad.**

### Rutas degeneradas y balance — la cola, que era la pregunta original

| Brazo | degeneradas/réplica | peor balance (réplica) | filas balance <0.60 |
| --- | ---: | ---: | ---: |
| `actual` | 0.2±0.4 | 0.803 | 0 |
| `cluster-r0` | 1.6±0.5 | 0.011 | 7 |
| `cluster-r1` | 0.8±0.4 | 0.012 | 4 |
| `cluster-r2` | 0.6±0.5 | 0.668 | 0 |
| `cluster-r1-no-floor` | 2.6±0.8 | 0.011 | 28 |
| `warm-greedy` | 0.0±0.0 | 0.815 | 0 |
| `warm-cluster` | 0.0±0.0 | 0.791 | 0 |

Ningún brazo cluster mejora la cola que la serie intenta cerrar; todos la **empeoran** o la
dejan igual mientras rompen la factibilidad. `cluster-r2` es el mejor comportado (0 filas
<0.60, degeneradas en empate con `actual`), pero sigue con drops y con cruces +89 %.

### Brazo B — arranque en caliente, y la Predicción 4 refutada

`reference-n1607`, media ± desviación:

| Brazo | drops | k | cruces | Δ cruces | travel | Δ travel |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `actual` | 0 | 25.0±0.0 | 68.2±6.0 | — | 60 941±957 | — |
| `warm-greedy` | 0 | 27.0±0.0 | 81.8±0.4 | **+19.9 % (real)** | 72 651±2 | **+19.2 % (real)** |
| `warm-cluster` | 7 filas | 34.8±0.7 | 341.8±92.4 | +401 % (real) | 73 159±4 336 | +20.0 % (real) |

**`warm-greedy` no se lava: ancla, y ancla duro.** En `n=1607` las cinco réplicas devuelven
**la misma solución** (travel 72 650±2, cruces 82±0.4, k 27): la GLS, con el límite topado en
120 s, **no escapa de la cuenca del greedy en absoluto**. La Predicción 4 —"se lava, empate en
las 12 instancias"— queda **refutada**: la diferencia contra `actual` es real y grande. El
falsador pre-registrado se activó: *"si `warm-cluster` difiere de `actual` de forma real bajo
la regla de varianza en `reference-n1607`, la lectura de meseta del ciclo anterior era
demasiado general y hay que matizarla."*

El matiz correcto: `multistart-sweep-20260721` midió que **permutar el orden de nodos de la
misma heurística** se lava, y eso sigue siendo cierto. Pero sembrar una **construcción
estructuralmente distinta** *no* se lava a `n=1607` —**se conserva**—, porque con el límite
topado en 120 s la corrida está lejos de converger en términos relativos. La meseta de aquel
ciclo era una meseta *alrededor del punto de construcción de `PATH_CHEAPEST_ARC`*; un punto
de partida lejano cae fuera de ella y la GLS no tiene tiempo de volver.

**Y aun así no sirve**, porque el punto de partida que se conserva es **peor**: la geometría
del greedy (vecino más cercano miope) tiene más travel y más cruces que la de
`PATH_CHEAPEST_ARC`, y anclar a ella arrastra el resultado hacia abajo. `warm-cluster` es
todavía peor porque su semilla de `cluster_first` ya viene con drops. El arranque en caliente
sólo ayudaría con una semilla **mejor** que la construcción por defecto, y no la hay: ése es
justamente el motivo por el que la serie usa `PATH_CHEAPEST_ARC`.

Fuera de `n=1607`, donde el límite de tiempo **no** está topado (`30 + 1.5·n < 120`), la GLS
sí tiene holgura para converger y `warm-greedy` se acerca a `actual` —consistente con la
lectura de meseta—, pero nunca lo supera. En `area-27` y `area-29` incluso baja cruces
(−57 %, −37 %) por debajo de `actual`, pero son empates bajo la regla de varianza y el travel
no mejora.

---

## Estado de cada criterio

Ningún brazo llega a evaluarse limpio en `n=1607` salvo `actual` (control) y `warm-greedy`:
todos los demás tienen drops. Para los dos sin drops:

| Criterio | `warm-greedy` | ¿Pasa? |
| --- | --- | :---: |
| n=1607 cruces −≥30 % | +19.9 % (real) | ❌ |
| n=1607 travel ≤+3 % | +19.2 % (real) | ❌ |
| n=1607 k ≤26 | 27.0±0.0 | ❌ |
| Áreas: `relleno_msf` −≥30 % | +2.6 % / +0.2 % / −0.5 % | ❌ |
| Áreas: cruces sin empeorar | mejoran o empatan | ✅ |
| Drops = 0 | 0 en 60 filas | ✅ |
| Balance ≥0.60 en toda instancia | 0 <0.60 | ✅ |
| 0 rutas degeneradas | 0.0±0.0 | ✅ |

**Cuatro de ocho.** Los brazos con drops (`cluster-r{0,1,2}`, `cluster-r1-no-floor`,
`warm-cluster`) fallan `0 drops` de entrada y no se evalúan más allá.

---

## Veredicto

**Las dos hipótesis del ciclo quedan falsadas.**

**Brazo A (clusters blandos):** restringir el espacio factible con
`SetAllowedVehiclesForIndex` (vía dominio de `VehicleVar`) **no** produce coherencia
espacial útil. kmeans no respeta la capacidad, así que en las instancias grandes crea
clusters que no caben en sus vehículos y el modelo **abandona árboles** (302 nodos a `r=0`,
41 aún a `r=2`); y donde sí cabe, quitarle al solver la elección de vehículo **dispara los
auto-cruces** (+89 % a +590 %) en vez de reducirlos. El brazo falla `0 drops`, falla cruces y
falla travel. La partición territorial previa, aunque sea "blanda", reintroduce exactamente
la patología de aislamiento que produjo la ruta degenerada de `b095`.

**Brazo B (arranque en caliente):** no se lava a `n=1607` —la meseta del ciclo de
multi-arranque era local al punto de construcción por defecto— pero **ancla a una geometría
peor**, porque no existe una semilla de construcción mejor que `PATH_CHEAPEST_ARC`. Falla
cruces y travel.

**No hay ganadora verificada en este ciclo, y no se dice esa frase.** No se cambia ningún
default de producción. Los mecanismos quedan implementados pero **opt-in**
(`--only-cell cluster-r{0,1,2}`, `warm-greedy`, `warm-cluster`); sin las banderas el pipeline
recorre el mismo camino de código de siempre.

### Lo que queda establecido

1. **La palanca tampoco está en el espacio factible tal como lo restringe un cluster
   geométrico.** La serie ya había cerrado el *precio* (penalizaciones) y la *búsqueda*
   (multi-arranque); este ciclo cierra la tercera vía que quedaba —*qué soluciones están
   disponibles*— **por partición espacial previa**. El resultado es que una partición que
   ignora la capacidad no acota el espacio a las buenas soluciones: lo acota a soluciones
   **infactibles**, y el solver responde abandonando árboles.
2. **El aislamiento de los tres árboles a 2,8 h es del territorio, no del solver.** kmeans
   los separa en un cluster de tamaño 1 en las cinco semillas (Fase 0, Predicción 2). La ruta
   degenerada de `b095` no era un accidente del objetivo del VRP: es la geometría del dataset
   la que fuerza una ruta *stub* para esos árboles, y cualquier método que respete la geografía
   —incluido un cluster blando— la reproduce. Esto **refuerza por un flanco nuevo** el cierre
   de `stops-penalty-sweep-20260722`: la palanca es `T_max`, el tiempo de servicio o la
   partición territorial *operativa* (no geométrica), no un término del modelo.
3. **La meseta del multi-arranque es local.** `multistart-sweep-20260721` concluyó que el
   punto de partida se lava; este ciclo lo acota: se lava para **perturbaciones del orden de
   nodos de la misma heurística**, pero una **semilla estructuralmente distinta se conserva**
   a `n=1607`, donde el límite de 120 s está topado. La lectura general "el arranque no
   importa" era demasiado amplia. No cambia la conclusión de adopción —la semilla que se
   conserva es peor— pero corrige el mecanismo, y es la primera vez que la serie mide el
   arranque en caliente en vez de deducirlo del multi-arranque.
4. **`0 drops` antes que cualquier métrica de calidad.** `cluster-r1-no-floor` habría pasado
   cruces, travel y relleno de áreas si se juzgara sólo por esas columnas; los pasa
   **abandonando 100 árboles**. El criterio de la serie ya ponía `0 drops` primero, y este
   ciclo es el caso que lo justifica con datos.

### Sobre la trampa declarada

Se declaró que un cluster mal dimensionado podía volverse infactible y que **eso era el
resultado, no algo a esconder ablandando la restricción**. Ocurrió: `r=0` abandona 302
árboles. **No se re-dimensionaron los clusters ni se subió `m` hasta que funcionara**; se
barrió `r` como estaba pre-registrado (0→1→2), se midió que aflojar reduce pero no elimina
los drops, y se reporta el brazo con sus drops. La disyunción viva (`-1` en el dominio del
`VehicleVar`) es lo que convirtió la infactibilidad en una señal medible en vez de un `None`.

### Adopción

Sin cambios. Los defaults de producción (`spatial_term`, `PenaltyConfig` actual, coeficiente
de span espacial 3) quedan intactos. Los clusters blandos y el arranque en caliente quedan
como mecanismos opt-in del driver de experimentación, disponibles para ciclos futuros pero
**no adoptados**.
