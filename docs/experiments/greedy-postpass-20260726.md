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

Pendiente: se completa tras correr los tres brazos.
