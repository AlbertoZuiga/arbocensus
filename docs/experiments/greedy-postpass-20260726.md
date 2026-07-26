# OR-Tools contra el greedy CON refinamiento, sobre `reference-n1607`

Fecha: 2026-07-26 · Rama: `docs/greedy-postpass-n1607`

> **Pre-registro.** Todo lo que sigue hasta la sección "Resultados" se escribió y se
> commiteó **antes** de correr ningún brazo. Los resultados se agregan después, sin
> editar el criterio.

## Por qué

La Tabla 2 de la tesis (`docs/thesis/secciones/03-resultados.tex`) compara la solución de
OR-Tools sobre `reference-n1607` contra un baseline greedy, y le atribuye a OR-Tools un
ahorro de 4 221 s (−6,7 %) en tiempo total de desplazamiento. Esa comparación tiene dos
defectos que la invalidan como está publicada:

1. **Refinamiento asimétrico.** Desde el PR #245 el post-pass 2-opt intra-ruta es default
   de producción, y la cifra de OR-Tools de la tabla (58 364 s) lo lleva aplicado. El
   greedy de la tabla no lleva refinamiento alguno. Comparar el método propio *con*
   refinamiento contra el competidor *sin* refinamiento mide el post-pass, no el solver.
2. **Líneas base de ciclos distintos.** La fila del greedy viene de
   `docs/experiments/20260713-greedy-baseline.csv`, corrida el 2026-07-13 sobre el mismo
   *conjunto* de árboles pero sobre otra fila `Dataset`. Los UUID difieren y
   `greedy_baseline` ordena los árboles por UUID
   (`backend/apps/optimization/management/commands/greedy_baseline.py:59`), así que el
   greedy es sensible a esa diferencia. Además, en esta serie la línea base se mueve más
   entre ciclos que entre semillas.

El flag `--postpass` de `greedy_baseline` ya existe (PR #261). Sobre las áreas reales le
dio al greedy entre −1,7 % y −22,5 % de travel. El margen de −6,7 % puede anularse o
darse vuelta.

## Qué se mide

Instancia congelada `reference-n1607` (`docs/experiments/instances/reference-n1607.csv`,
n = 1 607), cargada con `load_instances`, UUID de dataset determinista
`8c827643-dfa8-5f4a-8d57-25766d005fbd`.

Configuración censal idéntica en los tres brazos: servicio 2 min por árbol,
T_max = 3 h (10 800 s), T_min = 2 h (7 200 s), `SOLVER_TIME_LIMIT_SEC = 120`.

| brazo | comando | refinamiento |
| --- | --- | --- |
| `ortools` | `baseline_postpass --dataset reference-n1607 --seeds 42,43,44` (estrategia `spatial_term`) | post-pass 2-opt (default de producción) |
| `greedy-raw` | `greedy_baseline --dataset 8c827643-… ` | ninguno |
| `greedy-postpass` | `greedy_baseline --dataset 8c827643-… --postpass` | mismo post-pass 2-opt |

La línea base de OR-Tools **se vuelve a correr** en este ciclo; no se cita la corrida del
2026-07-24. Es la regla de la serie: todo reporte nuevo re-corre su propia línea base.

Los dos brazos greedy son deterministas (una corrida cada uno). El brazo OR-Tools corre
tres semillas; la semilla permuta el orden de los nodos antes de construir el modelo
(OR-Tools no expone semilla de RNG).

## Métricas reportadas

Por brazo: `k`, travel total (s), balance, σ de la duración por ruta, saturación **máxima**
(duración de la ruta más larga / T_max), rutas sobre T_max, drops, y rutas degeneradas por
**duración** (< 1 800 s).

Dos advertencias de metrología, que se repiten junto a la tabla de resultados:

- `baseline_postpass` reporta σ **muestral** (`statistics.stdev`) y `greedy_baseline` σ
  **poblacional** (`statistics.pstdev`). Con k ≈ 25 la diferencia es de ~2 %, pero se
  declara explícitamente en cualquier comparación de σ.
- `crossings` son autocruces **intra-ruta medidos sobre cuerdas rectas**, no sobre calles,
  y ya se demostró que se invierten respecto de la medición sobre calle
  (`docs/experiments/` — ciclo M16). **No son criterio aquí.** Se reportan como contexto o
  no se reportan. `interleave_per_route` es solape **entre** rutas: otra cosa, y tampoco es
  criterio.

## Criterio de veredicto (fijado antes de correr)

El objetivo del ciclo no es cambiar un default —esta rama no toca el solver ni ninguna
configuración de producción— sino decidir **qué dice la Tabla 2 de la tesis**.

Comparación primaria: travel total de OR-Tools (media de las tres semillas) contra el
travel del brazo `greedy-postpass`. Sea `sigma_seeds` la desviación estándar del travel
entre las tres semillas de OR-Tools, que es la incertidumbre de la cifra de OR-Tools.

- **OR-Tools gana en travel** si su travel medio es menor que el de `greedy-postpass` por
  un margen mayor que `sigma_seeds`.
- **Empate técnico** si el margen (en cualquier dirección) es menor o igual que
  `sigma_seeds`. Entonces la tesis no puede afirmar un ahorro de travel sobre el greedy
  refinado, y se dice así.
- **OR-Tools pierde en travel** si su travel medio supera al de `greedy-postpass` por más
  de `sigma_seeds`.

El margen contra `greedy-raw` se reporta también, porque es el que la tesis publica hoy y
hay que poder mostrar cuánto de ese −6,7 % era el post-pass.

Puertas independientes del travel, que se reportan gane quien gane y con las que se
juzga el plan como plan: `drops` (debe ser 0), rutas sobre T_max (debe ser 0), rutas
degeneradas por duración < 1 800 s, saturación máxima y balance.

## Declaración de publicación

**Si el margen se estrecha, se anula o se invierte, se publica igual.** El resultado se
escribe en este archivo y la Tabla 2 de la tesis se reescribe a tres columnas
(OR-Tools / greedy crudo / greedy + 2-opt) con la cifra que salga, incluida la nota al
pie y el texto que la rodea.

Si OR-Tools deja de ganar en travel, el argumento de la tesis **no se adorna ni se
rescata con métricas nuevas inventadas para la ocasión**: se reorienta a las dimensiones
ya declaradas arriba —rutas degeneradas, saturación máxima, holgura contra T_max y
balance— y se dice explícitamente que en travel la ventaja no se sostiene contra un
greedy que recibe el mismo refinamiento.

## Resultados

Corridos los tres brazos el 2026-07-26 sobre la instancia congelada recién cargada
(dataset `8c827643-dfa8-5f4a-8d57-25766d005fbd`, 1 607 árboles). CSV crudos:
`greedy-postpass-20260726-ortools.csv`, `-greedy-raw.csv`, `-greedy-postpass.csv`.

| métrica | OR-Tools (3 semillas) | greedy crudo | greedy + 2-opt |
| --- | --- | --- | --- |
| `k` | 25 | 24 | 24 |
| travel total (s) | **58 327** (σ entre semillas 1 538) | 63 073 | **61 234** |
| balance (mín/máx duración) | 0,835 | 0,930 | 0,908 |
| σ de la duración por ruta (s) | 559 (muestral) | 196 (poblacional) | 235 (poblacional) |
| saturación **media** | 93,0 % | 98,7 % | 98,0 % |
| saturación **máxima** | 99,4 % | 99,8 % | 99,8 % |
| rutas sobre T_max | 0 | 0 | 0 |
| drops | 0 | 0 | 0 |
| rutas degeneradas por duración (< 1 800 s) | 0 | 0 | 0 |
| ruta más pequeña (paradas / travel) | 6–12 / 7 798–8 666 s | 5 / 9 466 s | 5 / 9 466 s |
| tiempo de cómputo | 120 s (presupuesto) | 0,007 s | 0,09 s |

Travel por semilla de OR-Tools: 59 649 s (42), 56 640 s (43), 58 693 s (44). Las tres
difieren, así que **las semillas sí llegaron al solver**; y reproducen la corrida del
2026-07-24 (59 690 / 56 707 / 58 696) dentro de decenas de segundos.

### Veredicto según el criterio pre-registrado

**OR-Tools gana en travel.** Margen contra `greedy-postpass`: 2 907 s (**−4,75 %**), mayor
que `sigma_seeds` = 1 538 s. No es empate técnico.

Pero el margen **se estrecha**, y la cifra publicada estaba inflada por dos vías distintas
que se compensan en parte:

- Contra el greedy **crudo del mismo ciclo**, el ahorro es de 4 746 s (−7,52 %), *mayor*
  que el −6,7 % publicado. Es decir: la comparación cruzada de ciclos subestimaba el
  ahorro, no lo inflaba. El greedy sobre esta instancia congelada cuesta 63 073 s, no los
  62 585 s del CSV del 2026-07-13 — 488 s de diferencia por el orden de nodos que induce
  el UUID, tal como se anticipó.
- Darle al greedy el **mismo** post-pass 2-opt le quita 1 839 s (−2,92 %) y baja el ahorro
  de OR-Tools a −4,75 %. Ése es el efecto real de la asimetría de refinamiento: **el
  −6,7 % publicado se reduce a −4,75 %**, y algo más de un tercio del ahorro atribuido al
  solver era, en realidad, el post-pass que solo un lado recibía.

### Dos afirmaciones de la tesis que esta corrida refuta

No sobreviven al brazo nuevo, y hay que corregirlas en el texto:

1. **«Ninguna ruta de OR-Tools presenta esa patología».** Falso en las tres semillas. La
   ruta más pequeña de OR-Tools tiene 6–12 paradas con 7 798–8 666 s de desplazamiento;
   la del greedy tiene 5 paradas con 9 466 s. Es la misma patología, más suave: el solver
   la atenúa, no la elimina. Concuerda con el hallazgo del ciclo de clusters, donde el
   aislamiento de esos árboles resultó ser del territorio y no del solver.
2. **La holgura solo existe en la media.** OR-Tools promedia 93,0 % de T_max contra 98,0 %
   del greedy refinado, pero su **ruta más larga** llega al 99,4 % contra 99,8 %. En el
   peor caso —el que decide si un imprevisto de terreno rompe el plan— no hay ventaja
   apreciable. La holgura de OR-Tools es una propiedad del conjunto de rutas, no una
   garantía por ruta.

### Dimensiones donde el greedy no queda atrás

Tampoco se sostiene el reflejo de reorientar el argumento al balance:

- **Balance:** el greedy gana (0,930 crudo y 0,908 refinado, contra 0,835). Por la misma
  razón que le da menor σ: saturar toda ruta hasta el borde de T_max iguala duraciones.
  Saturación e igualdad de duraciones no se distinguen con esta métrica.
- **Rutas degeneradas por duración:** ninguna, en ningún brazo. Con la configuración
  censal esta puerta no separa a los métodos; la degeneración del greedy es **por
  paradas** (una ruta de 5 árboles), no por duración.

Lo que sí queda en pie a favor de OR-Tools, y es lo que la tesis puede afirmar: −4,75 % de
desplazamiento contra un competidor igualmente refinado, 93,0 % de saturación media contra
98,0 % (holgura agregada), y una ruta residual claramente menos patológica. El precio son
120 s de cómputo contra 0,09 s, y una ruta más (25 contra 24).

### Nota de metrología

Las σ de la tabla **no son comparables tal cual**: `baseline_postpass` usa
`statistics.stdev` (muestral) y `greedy_baseline` usa `statistics.pstdev` (poblacional).
Con k = 25 y k = 24 el factor es √(k/(k−1)) ≈ 1,02, así que la brecha 559 contra 235 no se
explica por ahí: es real.

`crossings` (45/63/58 en las semillas de OR-Tools) e `interleave_per_route` (166,5 en el
greedy) quedan registrados en los CSV como contexto. No entran en el veredicto, según lo
pre-registrado.

Las cifras **por ruta** de la columna de OR-Tools —saturación máxima (99,4 %) y ruta más
pequeña (6–12 paradas, 7 798–8 666 s)— **no quedan en el CSV**. `baseline_postpass`
calcula las filas por ruta con `audit_solution`
(`backend/apps/optimization/management/commands/baseline_postpass.py:55`) pero solo
persiste una fila agregada por semilla, así que re-derivarlas exige volver a correr la
instancia con `route_audit`, que sí emite una fila por ruta. Los dos rangos son sobre las
tres semillas y **no están emparejados**: la ruta más pequeña es una distinta en cada
semilla, de modo que el mínimo de paradas y el mínimo de desplazamiento no provienen
necesariamente de la misma ruta. El brazo greedy no tiene este problema:
`greedy_baseline` imprime `route,trees,travel_time_sec,estimated_time_sec` por ruta.
