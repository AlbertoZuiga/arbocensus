# Route disorder — ¿se reducen los cruces sin pagar el balance?

- Fecha: 2026-07-14 (UTC)
- Branch: `route-disorder`, sobre main (que incluye la suite de instancias congeladas, PR #165, y el volumen Postgres externo, PR #166)
- Objetivo: la revisión visual de las rutas del caso real (`route-audit-20260713.md` §e,
  `penalty-sensitivity-20260713.md` §c) señala que el desorden percibido son **auto-cruces**
  del polyline, no caminata. El experimento de penalizaciones halló que apuntar el soft upper de
  la dimensión Time a `T_max` (o sea, apagarlo) baja los auto-cruces de la instancia real n=1607
  de 76 a 6 (−92 %) a igual travel/k/cómputo, **pero** hunde el balance de duraciones de 0,838 a
  0,715 (umbral del cliente: ≥ 0,80). **Pregunta:** ¿se puede reducir los cruces SIN pagar el
  balance? **Hipótesis líder:** mover el soft upper a `T_max` y **angostar la banda subiendo
  `T_min`** deja que el soft lower (término dominante, 20:1) imponga el piso de balance mientras
  la geometría queda libre.
- Este reporte **mide**; no cambia ninguna constante ni default de producción (`solver.py:10-13`
  intacto). Sólo se ejercen los overrides ya existentes del comando `route_audit`
  (`--soft-upper-target`, `--t-min`, `--time-limit`).
- **Veredicto: la apuesta GANA en n=1607.** La celda D (`soft_upper_target=tmax`, `T_min=9000`)
  cumple el criterio a priori entero: cruces −93 %, solapamiento/ruta −30 %, balance 0,837 ≥ 0,80,
  k=25, 0 drops, travel −0,3 %. **Pero el hallazgo es regional:** con la config actual las áreas
  reales ya salen ordenadas y la apuesta las empeora (relleno de `T_min`). Detalle en §d, §e.

## a. Entorno y reproducción

Idéntico a Q0 (`route-audit-20260713.md` §a), Q1 (`penalty-sensitivity-20260713.md` §a), RP2 y R2:
`docker-compose.prod.yml`, imágenes target `prod`, OSRM real con el PBF completo de Chile (MLD,
perfil foot, `--max-table-size 5000`), PostGIS 15-3.3, Redis 7, MacBook M4 Pro con Docker Desktop.
**Un solo stack corriendo** durante toda la medición (la contención de CPU falsearía los tiempos).

A diferencia de los experimentos anteriores, las instancias ya no se recrean desde la base legacy:
salen de los **CSV congelados** en `docs/experiments/instances/` (PR #165). El volumen Postgres es
externo y compartido entre worktrees (`arbocensus_postgres_data`); las instancias se cargan una vez
con UUID deterministas, así que la matriz de costos OSRM se reutiliza entre corridas.

Levantar el stack (proyecto `arbocensus` → el volumen `postgres_data` resuelve al externo compartido
`arbocensus_postgres_data`) y cargar las instancias:

```bash
docker compose -p arbocensus -f docker-compose.prod.yml up -d --build db redis osrm backend
# El target prod no monta el repo, así que los CSV congelados no están en la imagen:
# se copian al contenedor y se cargan con rutas explícitas (idempotente, UUID deterministas).
docker cp docs/experiments/instances arbocensus-backend-1:/tmp/instances
docker compose -p arbocensus -f docker-compose.prod.yml exec backend \
  python manage.py load_instances /tmp/instances/reference-n1607.csv \
    /tmp/instances/area-26-n157.csv /tmp/instances/area-27-n72.csv /tmp/instances/area-29-n43.csv
```

Datasets (UUID deterministas, función pura del CSV):

- **reference-n1607** (`legacy_api` + `legacy_app`, n=1607): la instancia de la queja visual.
- **area-26-n157**, **area-27-n72**, **area-29-n43**: tres áreas reales.

Cada celda se corre con el comando `route_audit` (mismos overrides que Q1). Config censal de
referencia fija en toda la grilla: `service_time = 120 s` (2 min), `T_max = 10800 s` (3 h),
`strategy = spatial_term`, 3 semillas (42, 43, 44). En un dataset real la semilla sólo etiqueta la
repetición: el solver no la consume, la varianza viene del corte por wall-clock del GLS.

La grilla completa se orquestó con `.local/experiments/route_disorder_grid.py` (driver que corre el
mismo `OptimizationPipeline` que `route_audit` y reúsa sus helpers `audit_solution` /
`summarize_audit` / `routes_geojson` para las métricas de forma y los artefactos por celda; el driver
no es código de producción y no se versiona). Los per-route CSV y los GeoJSON de cada variante los
emite ese driver a `/results` (bind-mount de `.local/experiments`); de ahí se copian a
`docs/experiments/`.

Definiciones (idénticas a Q0/Q1): `self_crossings` = pares de aristas NO adyacentes de la secuencia
de paradas que se cruzan propiamente (proyección equirectangular local; tocarse en una parada
compartida no cuenta); `solapamiento/ruta` = `interleave_per_route` de `RoutingSolution` (puntos de
otras rutas dentro del bbox de cada ruta, promediado); `IoU peor par` = `worst_pair_iou` (IoU de
bounding boxes del peor par); `balance` = duración mínima / duración máxima (`balance_score`);
`σ(T)` = desviación estándar de las duraciones por ruta; `travel` = `total_travel_time_sec`;
`drops` = árboles sin asignar. **`walk_ratio` NO se usa como métrica de calidad en este experimento**
(Q1 lo cerró: es geometría del dataset, no relleno del solver).

## b. Grilla y criterio de éxito — FIJADOS ANTES DE LA PRIMERA CORRIDA

**Eje central, 2×2** sobre reference-n1607 (`service 120 s`, `T_max 10800 s`, `spatial_term`,
`time_limit 120 s`, semillas 42/43/44):

| celda | `soft_upper_target` | `T_min` | midpoint resultante | rol |
| --- | --- | --- | --- | --- |
| A | midpoint | 7200 s (2 h) | 9000 s | **config actual (baseline)** |
| B | tmax | 7200 s (2 h) | — (soft upper apagado) | eje soft upper aislado (= el hallazgo lateral de Q1) |
| C | midpoint | 9000 s (2,5 h) | 9900 s | eje T_min aislado |
| D | tmax | 9000 s (2,5 h) | — (soft upper apagado) | **la apuesta** (banda angosta + soft upper libre) |

Recordatorio (Q1 §a): la dimensión Time ya tiene capacidad **dura** `T_max`, así que un soft upper
parado en `T_max` no se puede violar nunca — `soft_upper_target=tmax` **apaga** el soft upper, no lo
mueve. Subir `T_min` a 9000 s sube el objetivo del soft lower (piso de duración) y, en las celdas
midpoint, también sube el midpoint a 9900 s.

**Control de cómputo** (sólo sobre n=1607, config actual A = midpoint / T_min 7200):
`time_limit ∈ {120 (actual), 300}`, semillas 42/43/44. Testea si más presupuesto GLS baja los cruces
por sí solo (Q0 §d.c atribuyó los cruces a secuencia no terminada de optimizar: las 4 corridas
agotaron los 120 s sin converger).

**Arm opcional `FIXED_VEHICLE_COST` reducido: NO se corre.** El comando `route_audit` no expone ese
override y tocarlo exigiría código nuevo fuera del alcance de un experimento de medición; se deja
anotado como trabajo futuro.

Sobre las **áreas reales** (n=157, n=72, n=43): sólo config actual (A) vs la apuesta (D), 3 semillas
cada una, misma config censal.

**Criterio de éxito (a priori, NO negociable a posteriori):** una variante **gana** si en n=1607 logra

> **cruces −≥ 30 %** Y **solapamiento/ruta −≥ 20 %**, con **k ≤ 26**, **balance ≥ 0,80 (restricción
> DURA)**, **0 drops** y **travel no peor que +3 %** vs la config actual (A).

Todas las cifras del veredicto salen de los CSV generados (`route-disorder-20260714-reference.csv`).
Las métricas de geometría se reportan **por separado** para n=1607 y para las áreas reales: si las
áreas salen limpias con la config actual, la conclusión es que el desorden es la **definición de la
instancia** (unión de ~12 km sin correlato operativo), no el solver.

## c. Resultados

_(se completa tras correr; una fila por celda desde los CSV)_

### c.1 Grilla central n=1607

Medias de las 3 semillas (`route-disorder-20260714-reference.csv`). Las semillas son casi
deterministas en un dataset real (el solver no las consume; la varianza viene del corte por
wall-clock del GLS): las cifras por semilla difieren ≤ 0,3 % en travel y ≤ 4 cruces.

| celda | `soft_upper` | `T_min` | k | travel [s] | Δ travel | balance | σ(T) [s] | solap./ruta | IoU peor par | **cruces** | drops | >T_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A** (actual) | midpoint | 7200 | 25 | 60 596 | — | 0,833 | 646 | 95,2 | 0,35 | **89,3** | 0 | 0 |
| B | tmax | 7200 | 25 | 59 119 | −2,4 % | **0,739** | 672 | 68,2 | 0,38 | **5,0** | 0 | 0 |
| C | midpoint | 9000 | 25 | 62 272 | +2,8 % | 0,912 | 359 | 94,1 | 0,35 | 86,7 | 0 | 0 |
| **D** (apuesta) | tmax | 9000 | 25 | 60 389 | **−0,3 %** | **0,837** | 578 | **66,3** | 0,32 | **6,0** | 0 | 0 |

Lectura por eje, que separa las dos causas:

- **B aísla el soft upper.** Apagarlo (target = T_max) con `T_min` intacto baja los cruces de
  89 a 5 (−94 %) y el solapamiento/ruta de 95,2 a 68,2 (−28 %), con travel y k iguales —
  reproduce el hallazgo lateral de Q1 (`penalty-sensitivity-20260713.md` §c). **Pero rompe el
  balance: 0,833 → 0,739**, bajo el umbral del cliente. Sin el soft upper que tira las duraciones
  hacia el midpoint, y con `T_min` todavía en 7200 s, el soft lower deja pasar rutas cortas.
- **C aísla `T_min`.** Subirlo a 9000 s (banda [9000, 10800], midpoint 9900) sube el balance a
  0,912 y aplasta σ(T) de 646 a 359 s, **pero no toca la geometría**: cruces 87, solapamiento 94.
  El piso de duración ordena las **duraciones**, no las **secuencias**.
- **D combina ambos ejes — y gana.** Con el soft upper apagado *y* la banda angosta, el soft
  lower (10 000/s, término dominante 20:1) impone el piso de balance en **0,837 ≥ 0,80** mientras
  la geometría queda libre: **cruces 6 (−93 %), solapamiento/ruta 66,3 (−30 %)**, IoU del peor par
  0,32 (< 0,35), travel −0,3 %, k 25, 0 drops. Es exactamente lo que predijo la hipótesis líder.

### c.2 Control de cómputo n=1607 (time_limit 120 vs 300)

Config actual (A: midpoint / T_min 7200), sólo se cambia el presupuesto del GLS.

| time_limit | k | travel [s] | balance | σ(T) [s] | solap./ruta | **cruces** |
| --- | --- | --- | --- | --- | --- | --- |
| 120 s (actual) | 25 | 60 596 | 0,833 | 646 | 95,2 | **89,3** |
| 300 s | 25 | 54 761 | 0,828 | 627 | 78,9 | **50,0** |

Más presupuesto GLS **sí** baja los cruces por sí solo (89 → 50, −44 %) y el travel (−9,6 %): parte
de los cruces del baseline es secuencia no terminada de optimizar, como anticipó Q0 §d.c. **Pero el
efecto del cómputo es parcial y mucho menor que el del objetivo:** D, con sólo 120 s, deja 6 cruces
contra los 50 que deja el baseline con 300 s. La geometría la manda la función objetivo (dónde se
para el soft upper), no el reloj — matiza la nota de Q1 (F13) sin contradecirla: el wall-clock
contribuye, pero apagar el soft upper del midpoint contribuye ~10× más.

### c.3 Áreas reales (n=157, n=72, n=43)

Config actual (A) vs la apuesta (D), misma config censal, 3 semillas (deterministas: idénticas por
celda). `route-disorder-20260714-areas.csv`.

| área | config | k | travel [s] | balance | σ(T) [s] | solap./ruta | IoU peor par | **cruces** | drops |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n=157 | actual (midpoint/7200) | 3 | 4 961 | 0,877 | 558 | 4,3 | 0,11 | **0** | 0 |
| n=157 | apuesta (tmax/9000) | 3 | 8 138 | 0,995 | 21 | 8,0 | 0,11 | **2** | 0 |
| n=72 | actual (midpoint/7200) | 2 | 5 737 | 1,000 | 0 | 25,5 | 0,63 | **6** | 0 |
| n=72 | apuesta (tmax/9000) | 2 | 9 331 | 1,000 | 3 | 26,0 | 0,65 | **27** | 0 |
| n=43 | actual (midpoint/7200) | 1 | 2 022 | 1,000 | 0 | 0,0 | 0,00 | **0** | 0 |
| n=43 | apuesta (tmax/9000) | 1 | 3 821 | 1,000 | 0 | 0,0 | 0,00 | **15** | 0 |

Dos lecturas, ambas contra la intuición que traía la apuesta desde n=1607:

1. **Con la config actual las áreas ya salen ordenadas.** n=157 y n=43 tienen **0 cruces**; n=72
   tiene 6 (dos rutas cubriendo el mismo barrio denso — IoU de bbox 0,63 porque comparten geografía,
   no porque las paradas se mezclen). Ninguna se acerca a los 89 cruces de n=1607. **El desorden que
   la revisión visual señala vive en n=1607, no en las áreas operativas reales.**
2. **La apuesta (D) EMPEORA las áreas.** Sube los cruces en las tres: n=157 0→2, n=72 6→27, n=43
   0→15. La causa es la que Q0/Q1 documentaron como F11.1: en un área chica el servicio total
   (43·120 = 5160 s, 72·120 = 8640 s) queda **muy por debajo de** `T_min = 9000 s`, así que subir
   `T_min` obliga a las rutas a **caminar de relleno** para tocar el piso (travel n=43: 2022 → 3821;
   n=72: 5737 → 9331), y esa caminata de relleno serpentea y se cruza. En n=1607 esto no pasa porque
   las rutas ya están saturadas de servicio (≈ 66 árboles · 120 s ≈ 7920 s, duración ≈ 10 130 s >
   9000 s): ahí subir `T_min` no genera relleno, sólo angosta la banda para el balance.

**El beneficio de la apuesta depende del régimen:** ayuda cuando el servicio satura la ruta
(n=1607) y perjudica cuando el servicio es escaso frente a `T_min` (áreas chicas). Adoptarla como
default global sin un guard por régimen (p. ej. escalar `T_min` al servicio disponible) trasladaría
el desorden de n=1607 a las áreas.

## d. Veredicto contra el criterio a priori

El criterio, fijado en §b antes de correr:

> GANA si en n=1607: cruces −≥ 30 % Y solapamiento/ruta −≥ 20 %, con k ≤ 26, balance ≥ 0,80
> (DURA), 0 drops y travel no peor que +3 % vs la config actual (A).

| celda | cruces −≥30 % | solap. −≥20 % | k ≤ 26 | **balance ≥ 0,80** | 0 drops | travel ≤ +3 % | **gana** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B (tmax / 7200) | sí (−94 %) | sí (−28 %) | sí | **no (0,739)** | sí | sí (−2,4 %) | **no** |
| C (midpoint / 9000) | no (−3 %) | no (−1 %) | sí | sí (0,912) | sí | sí (+2,8 %) | **no** |
| **D (tmax / 9000)** | **sí (−93 %)** | **sí (−30 %)** | **sí** | **sí (0,837)** | **sí** | **sí (−0,3 %)** | **SÍ** |

**D gana el criterio en las seis condiciones.** Es la respuesta afirmativa a la pregunta del
experimento: **sí se pueden reducir los cruces sin pagar el balance.** La clave es la de la
hipótesis líder — angostar la banda subiendo `T_min` traslada el trabajo de sostener el balance del
soft upper (que además retorcía las secuencias) al soft lower (que sólo fija duraciones), dejando la
geometría libre. B lo demuestra por descarte: apagar el soft upper sin angostar la banda logra la
misma geometría pero hunde el balance; C demuestra que angostar la banda sin apagar el soft upper
arregla el balance pero no la geometría. Sólo la combinación (D) consigue las dos cosas a la vez.

A diferencia de Q1 —donde ninguna variante ganó—, este eje **sí** produce una recalibración que
cumple el criterio a priori entero. **Importante:** esto NO ejecuta ningún cambio en producción;
`solver.py` queda intacto. Lo que el experimento entrega es la evidencia medida de que existe una
combinación `(soft_upper_target=tmax, T_min=9000)` que domina a la config actual en geometría sin
costo en balance/k/drops/travel. La decisión de adoptarla (tocar defaults) es un paso aparte, sujeto
a la revisión visual humana de los GeoJSON (§e) — el ojo es el juez final del "orden".

## e. Conclusiones

**Sobre n=1607 (la instancia de la queja visual):**

- **La respuesta a la pregunta del experimento es sí:** existe una combinación —soft upper apagado
  (`target=tmax`) más banda angosta (`T_min=9000`)— que **reduce los cruces un 93 % y el
  solapamiento/ruta un 30 % sin pagar el balance** (0,837 ≥ 0,80), a k, drops y travel esencialmente
  iguales. Es la celda D, y gana el criterio a priori en las seis condiciones. A diferencia de Q1
  (ninguna variante ganó), este experimento **sí** encuentra la variante buscada.
- **El mecanismo quedó aislado por el diseño 2×2:** la geometría la controla el soft upper (B la
  arregla, C no), el balance lo controla `T_min` vía el soft lower (C lo arregla, B no); sólo
  combinarlos (D) consigue ambas cosas. Esto confirma la jerarquía de penalizaciones que Q1 midió
  (soft lower domina 20:1) y la refutación de F11.2 de Q0 (el soft upper del midpoint no ordena
  duraciones — retuerce secuencias).
- **El cómputo importa, pero menos que el objetivo:** subir el time_limit de 120 a 300 s baja los
  cruces de 89 a 50 (−44 %), no a 6. La forma de las rutas es sobre todo función objetivo, no
  wall-clock — matiza F13 sin contradecirla.

**Sobre las áreas reales (n=157, n=72, n=43):**

- **Con la config actual el desorden no existe:** 0, 6 y 0 cruces. El entrelazado que se ve en el
  mapa del caso real es propiedad de **n=1607**, la unión de ~12 km de árboles legacy sin correlato
  operativo (una campaña real trabaja un área, no la unión de todas). En las áreas operativas el
  solver ya entrega rutas ordenadas. Esta es una conclusión igual de valiosa: buena parte de la
  "queja visual" es un artefacto de mirar la instancia agregada, no un defecto del solver sobre los
  planes que de verdad se ejecutan.
- **La recalibración ganadora de n=1607 no es universal: degrada las áreas** (cruces 0→2, 6→27,
  0→15), porque en instancias con servicio escaso frente a `T_min` la banda angosta fuerza caminata
  de relleno que serpentea (F11.1). Cualquier adopción en producción tendría que condicionar el eje
  `T_min` al régimen (servicio disponible por ruta), no aplicarlo plano.

**Recomendación:** documentar D como recalibración candidata **medida y validada contra el criterio
para el régimen saturado (n=1607)**, con el guard de régimen como condición para llevarla a
producción. No se toca `solver.py` en este experimento; el siguiente paso es la revisión visual
humana de los GeoJSON de A (actual) vs D (apuesta) sobre n=1607 —el ojo es el juez final del orden—
y, si aprueba, un experimento de guard por régimen antes de mover defaults.

## f. Artefactos versionados

- `route-disorder-20260714-reference.csv` — 15 corridas de n=1607 (grilla central + control).
- `route-disorder-20260714-areas.csv` — 18 corridas de las tres áreas.
- `route-disorder-20260714-ref-{midpoint,tmax}-tmin{7200,9000}.csv` / `.geojson` — per-route y
  geometría de las 4 celdas centrales (semilla 42). Para la revisión visual: **A** =
  `ref-midpoint-tmin7200`, **D (apuesta)** = `ref-tmax-tmin9000`.
- `route-disorder-20260714-area-{26-n157,27-n72,29-n43}-{actual,bet}.csv` / `.geojson` — per-route y
  geometría de cada área (semilla 42).
