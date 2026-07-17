# Sensibilidad a las penalizaciones del solver (test causal del relleno de caminata hasta T_min)

- Fecha: 2026-07-13 (UTC)
- Branch: `feat/penalty-sensitivity` (PR #162), sobre main `c51efad` (que ya incluye la radiografía de rutas `route-audit-20260713.md`, PR #154)
- Objetivo: test causal de la **hipótesis de relleno** ("quedar corto de T_min se arregla
  caminando", confirmada en régimen disperso por `route-audit-20260713.md`) y del eje del soft
  upper reformulado por esa radiografía (que refutó que el soft upper empuje las duraciones al
  midpoint: se paga en 25/25 rutas sin bajar ninguna → ¿sirve de algo, o conviene apuntarlo a
  T_max?). Este reporte mide; **no cambia ninguna constante ni default de producción**
  (`solver.py:9-12` intacto; el PR solo añade overrides al comando).
- **Veredicto: la recalibración NO gana bajo el criterio a priori.** Detalle en §d.
- Datos crudos (versionados junto a este reporte):
  - `penalty-sensitivity-20260713-disperse.csv` — una fila por corrida, 18 corridas del disperso
  - `penalty-sensitivity-20260713-reference.csv` — una fila por corrida, 18 corridas de la referencia
  - `penalty-sensitivity-20260713-{disp,ref}-slp{10000,100,0}-{midpoint,tmax}.csv` — tablas por ruta
    de las 12 variantes (semilla 42; las semillas 43 y 44 están en los dos CSV agregados)

## a. Entorno y reproducción

Idéntico a `route-audit-20260713.md` §a, `profiling-20260711.md` y `route-quality-20260712.md`: `docker-compose.prod.yml`, imágenes target
`prod`, OSRM real con el PBF completo de Chile (MLD, perfil foot, `--max-table-size 5000`),
PostGIS 15-3.3, Redis 7, MacBook M4 Pro con Docker Desktop. El worktree nace con volúmenes vacíos:
ambos datasets se recrearon y la primera matriz de cada uno se pagó en frío.

Levantar el stack:

```bash
docker compose -f docker-compose.prod.yml up -d --build db redis osrm backend
```

Recrear los datasets (mismos comandos que `route-audit-20260713.md`; los UUID son nuevos porque el volumen es nuevo):

```bash
docker compose -f docker-compose.prod.yml run --rm backend python manage.py shell -c "
from apps.datasets import legacy
rows = legacy.list_trees()
loaded = legacy.load_selection([(r['source'], r['external_id']) for r in rows])
full = legacy.create_dataset('Penalty sensitivity - legacy completo (ambas fuentes)', loaded)
print('FULL', full.id, full.total_trees)
"

docker compose -f docker-compose.prod.yml run --rm backend python manage.py seed_demo \
  --trees 40 --seed 42 --distribution uniform \
  --name "Penalty sensitivity - seed_demo disperso n40" --no-optimize
```

- **Referencia** (legacy completo, ambas fuentes, n=1607): `69ba2d85-cf39-4fda-afab-ff47ab8ec647`
- **Disperso sintético** (n=40, uniforme sobre Santiago): `7c634f93-d0f9-4830-ab3e-64a033560a0c`

Las 36 corridas salen del comando `route_audit` con los overrides nuevos del PR #162
(`--soft-lower-penalty`, `--soft-upper-target`, `--soft-upper-penalty`). Una corrida se ve así:

```bash
docker compose -f docker-compose.prod.yml run --rm -e PYTHONUNBUFFERED=1 backend \
  python manage.py route_audit \
    --dataset 7c634f93-d0f9-4830-ab3e-64a033560a0c --strategy spatial_term \
    --service-time 300 --t-min 7200 --t-max 10800 --time-limit 120 \
    --soft-lower-penalty 0 --soft-upper-target tmax --seed 42 \
    --csv /results/penalty-disp-slp0-tmax-s42.csv \
    --geojson /results/penalty-disp-slp0-tmax-s42.geojson
```

La grilla completa (3 penalizaciones × 2 objetivos × 3 semillas, por dataset) se corrió con
`.local/penalty-grid.sh <tag> <dataset> <service-time>`; los agregados por corrida se producen con
`.local/penalty-aggregate.py`. `--soft-upper-penalty` se dejó en su valor de producción (500) en toda
la grilla: el eje que `route-audit-20260713.md` dejó abierto es **dónde** se para el soft upper, no cuánto cuesta.

Cómo leer la columna `soft upper`: la dimensión Time ya tiene capacidad **dura** `T_max`
(`AddDimension(..., max_route_time_sec, ...)`), así que un soft upper parado en T_max no se puede
violar nunca. `soft_upper_target=tmax` no *mueve* la penalización: la **apaga**, y `soft_upper_penalty`
queda inerte en esas tres filas. Las variantes "T_max" se leen entonces como "sin soft upper".

Definiciones (idénticas a `route-audit-20260713.md`, más una): `walk_ratio` = caminata / duración;
**`cobertura del hueco de T_min`** = caminata / max(0, T_min − servicio), promediada sobre las
rutas cuyo servicio no llega a T_min — es la firma del relleno de caminata (una ruta que "camina para llegar a
T_min" cubre ≈100 % de su hueco); `saturación` = duración / T_max; `balance` = duración mínima /
duración máxima (el `balance_score` de `RoutingSolution`); `cruces` = auto-cruces del polyline.

Nota de determinismo: con la matriz OSRM caliente, las tres semillas de una misma variante dan
resultados idénticos o casi (el solver no consume la semilla; solo etiqueta la repetición y expone
la variación por corte de wall-clock del GLS, que aquí fue de ≤0,1 % en travel). Las tablas de §b
y §c reportan la semilla 42; los CSV agregados traen las tres.

## b. Grilla del disperso n=40 (el caso patológico de la hipótesis, service 300 s)

| slp | soft upper | k | travel [s] | T̄ [s] | σ(T) [s] | balance | **walk_ratio** | cobertura hueco | sat. media | shortfall [s] | drops | >T_max | cruces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 000 (actual) | midpoint (actual) | 4 | 23 427 | 8 857 | 210 | 0,952 | **0,661** | 1,405 | 0,820 | 0 | 0 | 0 | 0 |
| 10 000 | T_max | 4 | 22 778 | 8 694 | 1 232 | 0,718 | 0,655 | 1,389 | 0,805 | 0 | 0 | 0 | 0 |
| 100 | midpoint | 4 | 23 427 | 8 857 | 210 | 0,952 | 0,661 | 1,405 | 0,820 | 0 | 0 | 0 | 0 |
| 100 | T_max | 4 | 22 390 | 8 598 | 1 327 | 0,696 | 0,651 | 1,365 | 0,796 | 0 | 0 | 0 | 0 |
| 0 | midpoint | 4 | 23 469 | 8 867 | 249 | 0,926 | 0,662 | 1,398 | 0,821 | 0 | 0 | 0 | 0 |
| 0 | T_max | 4 | 22 072 | 8 518 | 1 584 | 0,591 | **0,648** | 1,369 | 0,789 | 1 091 | 0 | 0 | 0 |

**El walk_ratio del disperso es un piso duro: 0,648–0,662 en las seis variantes** (rango total: 1,4
puntos). El criterio a priori pedía ≤0,520. Quitar por completo la penalización de T_min
(slp = 0) mueve el walk_ratio en **−1,3 puntos**, no en los 15 exigidos.

Por qué: en este dataset la caminata **no es solo relleno**. Las 4 rutas tienen 7–12 árboles
repartidos por toda la ciudad; sin ninguna presión de duración, visitar esos árboles ya cuesta
~22 000 s de caminata contra 12 000 s de censo. La cobertura del hueco (1,37–1,41) lo dice: la
caminata excede el hueco a T_min en ~40 %, o sea que **incluso descontando todo el relleno la
caminata seguiría dominando al servicio**. La hipótesis de relleno sigue siendo cierta —la duración se detiene justo
sobre T_min y el shortfall es 0 en 5 de las 6 variantes—, pero el margen que el relleno explica es
chico frente a la geometría del dataset.

(Diferencia con `route-audit-20260713.md`: allá el baseline del disperso dio k=5 y walk 0,670 con cobertura 100–105 %;
aquí da k=4, walk 0,661 y cobertura 141 %. Mismo dataset, misma configuración: es una partición
distinta a la que llegó el GLS dentro de los mismos 120 s. La firma del relleno de caminata —duraciones clavadas
apenas sobre T_min, shortfall 0— se reproduce en ambas; la magnitud exacta de la cobertura del
hueco depende de cuántas rutas abra el solver, así que **se lee como indicador cualitativo, no como
cifra fina**.)

## c. Grilla de la referencia n=1607 (control de no-regresión, service 120 s)

| slp | soft upper | k | travel [s] | Δ travel | T̄ [s] | σ(T) [s] | balance | walk_ratio | sat. media | shortfall [s] | drops | >T_max | cruces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 000 (actual) | midpoint (actual) | 25 | 59 372 | — | 10 088 | 634 | 0,838 | 0,235 | 0,934 | 0 | 0 | 0 | 76 |
| 10 000 | T_max | 25 | 58 696 | −1,1 % | 10 061 | 822 | 0,715 | 0,233 | 0,932 | 0 | 0 | 0 | **6** |
| 100 | midpoint | 26 | 62 889 | +5,9 % | 9 836 | 640 | 0,831 | 0,246 | 0,911 | 0 | 0 | 0 | 77 |
| 100 | T_max | 25 | 58 317 | −1,8 % | 10 046 | 827 | 0,708 | 0,232 | 0,930 | 0 | 0 | 0 | 10 |
| 0 | midpoint | **32** | 77 533 | +30,6 % | 8 449 | 583 | 0,739 | 0,287 | 0,782 | 324 | 0 | 0 | 35 |
| 0 | T_max | 25 | **50 762** | **−14,5 %** | 9 744 | 2 116 | **0,011** | 0,208 | 0,902 | 7 080 | 0 | 0 | 10 |

El baseline reproduce la referencia publicada y la corrida R1 de `route-audit-20260713.md`: k=25, 0 drops, 0 excesos de
T_max, walk 0,235 (`route-audit-20260713.md`: 0,233), travel 59 372 s (`route-audit-20260713.md`: 58 664 s, dentro de la variación por corte de
wall-clock del GLS ya documentada).

Tres lecturas:

1. **slp = 0 + T_max baja el travel un 14,5 % — y rompe el balance.** Es la única variante que pasa
   el umbral de travel del criterio, pero lo compra con una **ruta degenerada: 1 árbol, 120 s de
   duración** (`penalty-sensitivity-20260713-ref-slp0-tmax.csv`, ruta 1). Ese único árbol hunde el
   balance a 0,011 y explica el σ de 2 116 s. Sin ninguna penalización por quedar corto, al solver
   le sale barato dejar un árbol suelto en su propio "turno" de 2 minutos y ahorrarse el travel de
   integrarlo. Las otras 24 rutas quedan sanas (7 354–10 748 s), pero un plan con un censista que
   trabaja dos minutos no es entregable: **el balance de carga es requisito del cliente**, y este es
   exactamente el modo de falla que el criterio a priori anticipó al exigir balance ≥ 0,80.
2. **Bajar la penalización de T_min sin mover el soft upper empeora todo.** slp = 100 abre una ruta
   más (k=26) y sube el travel 5,9 %; slp = 0 abre **siete** (k=32) y lo sube 30,6 %. Con el soft
   lower fuera de juego, el soft upper del midpoint pasa a mandar y parte las rutas para bajarlas a
   la banda: T̄ cae de 10 088 a 8 449 s (saturación 0,78). Más rutas, más cortas, y mucho más
   caminata total.
3. **Esto responde la hipótesis abierta de `route-audit-20260713.md`** ("con 25 rutas pagando ~1 060 s sobre el midpoint,
   ¿por qué el solver no abre más rutas: GLS que no llega, o el travel lo compensa?"). **Ninguna de
   las dos: es la jerarquía de penalizaciones.** El soft upper del midpoint no es inerte, está
   *dominado* — vale 500/s contra los 10 000/s del soft lower, factor 20. Abrir rutas para bajar al
   midpoint hunde las duraciones bajo T_min, y eso cuesta 20× más de lo que ahorra. Se ve al quitar
   el soft lower: misma instancia, mismo time_limit de 120 s, y k salta de 25 a 32 con las
   duraciones bajo el midpoint. El GLS **sí** alcanza esa configuración; con los pesos de hoy,
   simplemente no le conviene.

**Hallazgo lateral, fuera del criterio (relevante para la revisión visual de las rutas y su experimento de seguimiento):** mover el soft upper a T_max —o
sea, apagarlo, por lo dicho en §a— con la penalización de T_min intacta deja el travel casi igual
(−1,1 %), k igual (25), 0 drops, 0 excesos… y **baja los auto-cruces del polyline de 76 a 6**
(−92 %). El soft upper en el midpoint
está empujando al solver a secuencias que se cruzan; apuntarlo a T_max se lo lleva casi entero. El
costo es balance (0,838 → 0,715, bajo el umbral del cliente) y σ (634 → 822 s). No cumple el
criterio de este experimento —que se decide por walk_ratio y travel—, pero ataca justo la métrica que la revisión
visual señaló como la queja real. **Es material para un experimento de seguimiento sobre la geometría (realizado luego en `route-disorder-20260714.md`), no una recalibración aprobada.**

## d. Veredicto contra el criterio a priori

El criterio, fijado antes de correr:

> GANA la recalibración si walk_ratio del disperso baja ≥15 puntos (0,670 → ≤0,520) **o** travel de
> la referencia baja ≥5 %, **con** k ≤ 26, balance ≥ 0,80, 0 drops, 0 excesos de T_max.

| variante | walk disperso ≤0,520 | travel ref −≥5 % | k ≤ 26 | balance ≥0,80 | 0 drops | 0 >T_max | **gana** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 000 / midpoint (actual) | no (0,661) | — | sí | sí (0,838) | sí | sí | — |
| 10 000 / T_max | no (0,655) | no (−1,1 %) | sí | **no** (0,715) | sí | sí | **no** |
| 100 / midpoint | no (0,661) | no (+5,9 %) | sí | sí (0,831) | sí | sí | **no** |
| 100 / T_max | no (0,651) | no (−1,8 %) | sí | **no** (0,708) | sí | sí | **no** |
| 0 / midpoint | no (0,662) | no (+30,6 %) | **no** (32) | **no** (0,739) | sí | sí | **no** |
| 0 / T_max | no (0,648) | **sí (−14,5 %)** | sí | **no** (0,011) | sí | sí | **no** |

**Ninguna variante gana.** Ninguna acerca el walk_ratio del disperso al umbral (el mejor caso lo
mueve 1,3 puntos de los 15 pedidos), y la única que baja el travel de la referencia lo hace
degenerando el balance a 0,011 con una ruta de un árbol.

Las dos caras del trade-off, como pedía el criterio:

- **A favor de relajar:** con soft lower en 0 y soft upper en T_max, el travel del caso real cae
  8 610 s (−14,5 %) y el walk_ratio agregado baja de 0,235 a 0,208.
- **En contra:** ese ahorro sale de no obligar a nadie a llenar su turno. Aparecen rutas cortas
  (una de 120 s), el balance se desploma y el shortfall total pasa de 0 a 7 080 s. Las duraciones
  objetivo de 2–3 h son **requisito del cliente**, no capricho del solver: sin la penalización de
  T_min, el plan deja de cumplirlo.

## e. Decisión recomendada

**Documentar la limitación como trade-off inherente al diseño. No tocar `solver.py`.**

Justificación:

1. El criterio a priori no se cumple, y la única variante que roza el umbral de travel viola el
   requisito de balance de forma cualitativa (una ruta de un árbol), no marginal.
2. El caso patológico de la hipótesis (disperso n=40) resulta **insensible** a las penalizaciones: su
   walk_ratio 0,66 es geometría del dataset, no relleno. La cobertura del hueco de T_min (~140 %)
   muestra que la caminata excede el hueco: aunque el relleno desapareciera, la caminata seguiría
   duplicando al censo. Esto coincide con la lectura visual (ese dataset se ve "disperso por
   la ciudad", no con "vueltas innecesarias") y con que la queja humana apunte a los datasets de
   walk_ratio bajo.
3. El costo de reabrir el capítulo de resultados a dos semanas de la defensa no se justifica por un
   cambio que, en el caso real, o no mueve el travel (≤2 %) o rompe un requisito del cliente.

Lo que este experimento sí deja como material de tesis (§3.1.4 / limitaciones):

- **La función objetivo optimiza duración objetivo, no desplazamiento**, y ahora está medido
  causalmente: quitar la presión de T_min cambia el plan (k 25→32 o travel −14,5 % según el soft
  upper), luego las penalizaciones **son** la causa dominante de la forma de las rutas.
- **Por qué el solver no abre más rutas** (hipótesis abierta de `route-audit-20260713.md`): jerarquía de penalizaciones —
  soft lower 10 000/s domina 20:1 al soft upper 500/s. No es límite del GLS ni compensación del
  travel (§c.3).
- **El soft upper en el midpoint no es inerte, es dominado**: matiza la refutación (en `route-audit-20260713.md`) de que el soft upper empuje las duraciones al midpoint.
  Con el soft lower activo se paga en 25/25 rutas sin bajarlas; sin soft lower, empuja de verdad
  (k=32, T̄ 8 449 s).
- **Gancho para un experimento de seguimiento sobre la geometría (la revisión visual de las rutas):**
  `soft_upper_target=tmax` baja los auto-cruces de 76 a 6 con travel y k
  intactos, a costa del balance (0,715). La geometría de las rutas **sí** responde a este eje —
  justo la métrica que la revisión visual señaló. Ese experimento de seguimiento debería incluirlo en su grilla junto a
  `time_limit` y `FIXED_VEHICLE_COST`, midiendo balance como restricción dura (realizado luego en `route-disorder-20260714.md`).
