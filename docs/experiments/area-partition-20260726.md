# OR-Tools vs greedy sobre áreas reales, y precio de particionar

Fecha: 2026-07-26 · Rama: `docs/area-partition-benchmark`

## Por qué

La instancia de evaluación habitual, `reference-n1607`, es **agregada**: junta árboles de
dos fuentes legadas sobre una extensión de ~11,9 km que ningún censista recorre como una
sola unidad. Los árboles son reales; lo que no tiene correlato operativo es la agrupación.
Todo lo que se ha medido sobre ella describe un problema que nadie ejecuta.

Este ciclo mide sobre las áreas del censo antiguo, que sí son unidades operativas, y
además pone precio a la partición misma.

## Instancias

Congeladas en `docs/experiments/instances/`. Diámetro = distancia haversine máxima entre
dos árboles de la instancia.

| instancia | n | diámetro |
| --- | --- | --- |
| `area-26-n157` | 157 | 1 349 m |
| `area-27-n72` | 72 | 979 m |
| `area-29-n43` | 43 | 417 m |
| `areas-26-27-29-n272` | 272 | 2 685 m |

Las tres áreas son **disjuntas por identidad de árbol**: intersección vacía en las tres
parejas sobre la clave `(source, external_id)`, y 157 + 72 + 43 = 272 = |unión|. La trampa
de las áreas legadas duplicadas/anidadas (48 registros, 31 anillos) no muerde aquí, pero
la deduplicación por clave natural se hizo igual al construir la unión, porque el número
de áreas que sí se solapan es alto y la coincidencia no estaba garantizada de antemano.

## Brazos

Por cada instancia:

1. **OR-Tools producción** — `baseline_postpass --dataset <nombre> --seeds 42,43,44`,
   estrategia `spatial_term`, post-pass 2-opt activo (el default de producción),
   `SOLVER_TIME_LIMIT_SEC = 120`, T_min 7 200 s, T_max 10 800 s, servicio 120 s.
2. **Greedy crudo** — `greedy_baseline --dataset <uuid>`, vecino más cercano encadenado
   hasta agotar T_max. Determinista, sin semillas.
3. **Greedy + 2-opt** — `greedy_baseline --dataset <uuid> --postpass`, el mismo
   `resequence_routes` que corre el pipeline sobre la salida del solver.

El brazo 3 existe porque comparar el método propio *con* refinamiento contra un competidor
*sin* refinamiento no es defendible: mide el post-pass, no el solver.

Además, el contrafáctico de la partición: brazo 1 sobre `areas-26-27-29-n272` contra la
suma de los brazos 1 de las tres áreas por separado.

## Pre-registro

Escrito y commiteado **antes** de correr nada.

**Criterio contra el greedy.** El solver gana si, en las tres áreas y sobre el brazo 3
(greedy + 2-opt, el competidor fuerte):

- `travel_sec` del solver ≤ el del greedy+2-opt, **o** lo empeora en ≤ 5 % pero
- ninguna ruta queda saturada por sobre el 95 % de T_max, y
- `balance` del solver ≥ 0,80, contra rutas degeneradas del greedy.

El margen defendible se fija en **travel ±5 %** y en **saturación máxima**, no en
`crossings`: la métrica de autocruces se mide sobre cuerdas rectas y ya se demostró que
se invierte respecto de la medición sobre calles, así que aquí se reporta como contexto,
nunca como criterio.

Si el margen en travel se estrecha o se da vuelta, **se publica igual**. El respaldo del
solver no es el travel: es que el greedy satura sus rutas contra T_max y deja rutas
degeneradas, es decir, produce jornadas que un censista no puede ejecutar, mientras que
el solver reparte. Una derrota en travel con victoria en saturación y balance es el
resultado esperado y se reporta como tal.

**Criterio del precio de particionar.** Se espera que la partición **pierda travel** y
**gane tractabilidad y sentido operativo**:

- Σ(por área) `travel_sec` > unión `travel_sec` — particionar cuesta kilómetros, porque
  prohíbe rutas que crucen el borde entre áreas.
- Σ(por área) `k` ≥ unión `k` — más rutas, cada una más corta.
- `solve_time` de la unión > Σ(por área), aunque el presupuesto por corrida sea fijo.

Se declara de antemano: si sale al revés — si la unión pierde travel contra la suma de las
partes — se reporta igual, y significa que el solver no está aprovechando la instancia
grande, no que particionar sea gratis.

## Métricas y cómo NO leerlas

- `travel_sec`: tiempo de viaje total, sin servicio. Es la magnitud de costo.
- `k`: número de rutas.
- `balance`: evenness de carga entre rutas de una corrida.
- `saturation_mean` / `routes_over_t_max`: cuán pegadas a T_max quedan las rutas.
- `crossings`: **autocruces dentro de una misma ruta**, sobre cuerdas rectas, no sobre
  calles. No es "cruces" a secas y no es proxy de travel.
- `interleave_per_route`: **solape entre rutas distintas**. Otra cosa. Contexto.

Toda cifra de este reporte proviene de corridas de este mismo ciclo. No se compara contra
números publicados en reportes anteriores.

## Resultados

CSV crudos: `area-partition-ortools-<instancia>.csv` (una fila por semilla),
`area-partition-greedy-raw-<instancia>.csv` y `area-partition-greedy-postpass-<instancia>.csv`
(el greedy es determinista, una fila por instancia).

### Los tres brazos, por área

`travel` en segundos; OR-Tools = media de las 3 semillas. `sat_max` = duración de la ruta
más larga sobre T_max = 10 800 s, leída del stdout de cada corrida: los CSV de OR-Tools solo
traen `saturation_mean`. `σ ruta` **no es homogénea entre brazos**: `baseline_postpass` la
reporta muestral y `greedy_baseline` poblacional; con k = 3 la razón es √(3/2) ≈ 1,22, muy
por debajo de las diferencias de esta tabla.

| instancia | brazo | k | travel | balance | σ ruta (s) | sat_max | rutas > T_max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `area-26-n157` | OR-Tools | 3 | **4 859** | **0,872** | 569 | 0,77–0,82 | 0 |
| `area-26-n157` | greedy crudo | 3 | 5 900 | 0,301 | 3 539 | 0,998 | 0 |
| `area-26-n157` | greedy + 2-opt | 3 | 5 502 | 0,276 | 3 643 | 0,993 | 0 |
| `area-27-n72` | OR-Tools | 2 | 2 466 | 0,887 | 477 | 0,53–0,56 | 0 |
| `area-27-n72` | greedy crudo | 1 | 2 024 | 1,000 | 0 | 0,987 | 0 |
| `area-27-n72` | greedy + 2-opt | 1 | **1 569** | 1,000 | 0 | 0,945 | 0 |
| `area-29-n43` | OR-Tools | 1 | 984 | 1,000 | 0 | 0,57 | 0 |
| `area-29-n43` | greedy crudo | 1 | 1 007 | 1,000 | 0 | 0,571 | 0 |
| `area-29-n43` | greedy + 2-opt | 1 | **961** | 1,000 | 0 | 0,567 | 0 |
| `areas-26-27-29-n272` | OR-Tools | 5 | **9 462** | **0,896** | 421 | 0,82–0,83 | 0 |
| `areas-26-27-29-n272` | greedy crudo | 5 | 9 856 | 0,011 | 4 193 | 0,993 | 0 |
| `areas-26-27-29-n272` | greedy + 2-opt | 5 | 9 691 | 0,011 | 4 178 | 0,992 | 0 |

Ningún brazo dejó árboles sin asignar (`drops` = 0, `dropped_trees` = 0) ni rutas sobre T_max.

El post-pass 2-opt le sirve al greedy en las cuatro instancias: −6,7 % de travel en
`area-26`, −22,5 % en `area-27`, −4,6 % en `area-29`, −1,7 % en la unión. Es decir, el
brazo 3 no es decorativo: sin él la comparación habría sobrestimado al solver entre 2 y
22 puntos porcentuales.

### Veredicto contra el pre-registro: **no se cumple, 2 de 3 áreas**

- `area-26-n157`: **pasa**. Travel −11,7 % contra greedy+2-opt, balance 0,872 vs 0,276,
  ninguna ruta sobre 82 % de T_max. El greedy parte 157 árboles en 74 / 72 / **11**: dos
  jornadas al 99,3 % y 98,7 % de T_max y un muñón de 2 962 s (27 % de la jornada). El
  solver reparte 8 275 / 8 042 / 7 460 s. Este es el caso que el pre-registro anticipaba.
- `area-29-n43`: **pasa**. Travel +2,4 %, dentro del margen declarado de ±5 %; k=1 en los
  dos métodos y la misma jornada de ~6 100 s. La instancia es demasiado chica para
  distinguir métodos.
- `area-27-n72`: **falla, y no por poco**. El greedy mete los 72 árboles en **una** jornada
  de 10 209 s (94,5 % de T_max) con 1 569 s de viaje. El solver abre **dos** rutas
  (5 766 + 5 597 s) y gasta 2 466 s de viaje: **+57 % de travel** y dos medias jornadas en
  vez de una completa. No hay ruta degenerada que reprocharle al greedy: su solución es la
  que un censista querría.

**Por qué falla `area-27`, y es un fallo de búsqueda.** Con el arm de producción
(`balance_arm = actual`, el que corre `baseline_postpass`) las cotas blandas no dependen de
la instancia: piso en T_min = 7 200 s a 10 000/s y objetivo superior en el punto medio
`(T_min + T_max) / 2` = 9 000 s a 500/s, idénticos en las cuatro instancias. Verificado
llamando `PenaltyConfig.vehicle_bounds` con los parámetros de estas corridas: devuelve
`((7200, 10000), (9000, 500))` para las cuatro. El piso que sí escala con el servicio
(`min(T_min, servicio // max_vehicles)`) pertenece a los arms `tmin-scaled`, que no se
corrieron aquí.

Con esos precios, la jornada única de 10 209 s que encuentra el greedy paga
(10 209 − 9 000) × 500 ≈ 604 k de exceso más 100 k de costo fijo: **≈ 705 k**. Las dos rutas
del solver (5 766 y 5 597 s) caen **bajo el piso** y pagan
(7 200 − 5 766) × 10 000 + (7 200 − 5 597) × 10 000 ≈ 30,4 M más 200 k de costo fijo:
**≈ 30,6 M**. El objetivo prefiere la jornada única por un factor ≈ 43.

Es decir: el solver **no entregó lo que su propio objetivo pide**. La partición de `area-27`
es un óptimo local de la búsqueda, no una preferencia del modelo. El camino hacia la jornada
única es cuesta arriba: mover paradas de B a A empuja a A contra el techo de 9 000 s mientras
hunde a B más abajo del piso a 10 000/s, y el ahorro solo se cobra cuando B queda vacío, ya
que un vehículo vacío no paga ninguna cota. GLS penaliza arcos, no cumuls, así que no tiene
por qué remontar esa cuesta; las tres semillas caen en el mismo pozo.

Las otras tres instancias son consistentes con estos mismos precios y no con un piso
escalado: en `area-26` el solver deja las tres rutas en 8 275 / 8 042 / 7 460 s, dentro de la
banda [7 200, 9 000] donde no se paga nada, y en la unión las medias por semilla quedan en
8 204 / 8 121 / 8 936 s, también dentro. Con un piso de 2 355 s y techo de 6 577 s las rutas
de `area-26` pagarían entre 440 k y 850 k cada una y al solver le habría convenido abrir más.
`area-29` es el caso sin salida: 43 árboles no alcanzan para 7 200 s, así que su única ruta
paga el piso porque no hay alternativa.

Lo medido aquí no es entonces el subsidio a partir rutas del precio marginal, sino su
contrario: el piso es tan caro que la búsqueda no encuentra cómo cruzar el valle que lo
separa de la solución que el propio objetivo prefiere. El efecto es de +57 % de viaje y una
jornada de censista de más.

### Precio de particionar: la unión contra la suma de las partes

Las tres áreas son disjuntas, así que Σ(por área) y la unión resuelven exactamente los
mismos 272 árboles.

| magnitud | Σ(por área) | unión `n272` | lectura |
| --- | --- | --- | --- |
| travel medio (3 semillas) | 8 309 s | 9 462 s | la unión es 13,9 % **peor** |
| travel mediano | 8 272 s | 8 381 s | la unión es 1,3 % peor |
| travel por semilla (unión) | — | 8 381 / 7 964 / **12 040** | dispersión 51 % |
| k | 3 + 2 + 1 = **6** | **5** | particionar cuesta **una ruta** |
| balance | 0,872 / 0,887 / 1,000 | 0,896 | equivalente |
| saturación media | 0,732 / 0,514 / 0,569 | 0,780 | la unión llena mejor las jornadas |
| rutas bajo T_min (7 200 s) | 0 / **2** / **1** | **0** | la partición deja medias jornadas |
| presupuesto de solver | 3 × 360 s = 1 080 s | 360 s | particionar cuesta 3× de CPU |

**Sale al revés de lo pre-registrado en travel, y se reporta igual.** Particionar no cuesta
kilómetros aquí: las tres áreas están separadas (diámetros de 1 349, 979 y 417 m frente a
2 685 m de la unión), así que casi no hay ruta que gane cruzando el borde entre áreas. Lo
que la unión gana no es geometría sino *llenado*: con 272 árboles el solver arma 5 jornadas
de ~8 900 s en vez de 6 jornadas de las cuales 3 quedan bajo T_min.

La ventaja aparente de la partición en travel medio (−12,2 %) descansa casi entera en una
semilla: la 44 de la unión sale en 12 040 s contra 8 381 y 7 964 de las otras dos. Con la
mediana la diferencia cae a 1,3 %. La lectura honesta es que **al mismo presupuesto por
corrida (120 s), la instancia monolítica es menos estable**, no que particionar ahorre
viaje. Y ese presupuesto igual no es comparable: la partición consumió 3× el CPU total.

Así que el precio de particionar, medido, es: **una jornada de censista más, tres jornadas
por debajo de T_min, y 3× de CPU**, a cambio de instancias de ~1,3 km que corresponden a
una unidad operativa real y de una varianza entre semillas mucho menor.

### Contexto, no criterio

`crossings` (autocruces intra-ruta, medidos sobre cuerdas rectas, no sobre calles):
2,7 en `area-26`, 5,7 en `area-27`, 5,7 en `area-29`, 5,0 en la unión, siempre para
OR-Tools. `interleave_per_route` (solape entre rutas distintas): 5,9 / 19,0 / 0,0 / 28,4
para OR-Tools contra 31,0 / 0,0 / 0,0 / 30,6 del greedy. Ninguna de las dos entró en el
criterio y ninguna se usa aquí para sostener nada.

### Qué queda abierto

1. En áreas chicas la búsqueda no alcanza el óptimo de su propio objetivo. `area-27` es el
   caso mínimo reproducible: 72 árboles, una jornada al 94,5 % de T_max es factible y ≈ 43
   veces más barata, y las tres semillas devuelven dos medias jornadas. La verificación
   directa es barata: alimentar la solución de una ruta del greedy como warm start y ver si
   el solver la conserva. Si la conserva, es fallo de búsqueda confirmado y la palanca es la
   búsqueda (o un post-pass de fusión de rutas), no los precios.
2. La varianza entre semillas de la instancia grande (51 % de dispersión en travel) no está
   caracterizada: tres semillas no bastan para decir si la 44 es cola o modo.
