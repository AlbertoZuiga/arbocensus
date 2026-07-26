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

Pendiente: se completa con las corridas.
