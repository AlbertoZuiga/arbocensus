# Radiografía de las rutas actuales (walk_ratio, relleno por T_min, solapamiento)

- Fecha: 2026-07-13 (UTC)
- Branch: `experiment/route-audit` (sobre main `31631b7`, que incluye la instancia de referencia y el baseline greedy, PR #151)
- Objetivo: cuantificar la hipótesis de que las penalizaciones de duración dominan al
  término de desplazamiento y clasificar, ANTES de proponer cualquier recalibración, qué causa
  cada ruta visualmente sospechosa. Este reporte mide; no cambia ninguna constante ni
  default de producción.
- Datos crudos (versionados junto a este reporte):
  - `route-audit-20260713-r1.csv` / `.geojson` — referencia, spatial_term, n=1607
  - `route-audit-20260713-r2.csv` / `.geojson` — contraste, global, n=1607
  - `route-audit-20260713-r3.csv` / `.geojson` — área legacy 40, n=157, defaults de UI
  - `route-audit-20260713-r3b.csv` / `.geojson` — dataset disperso seed_demo, n=40, defaults de UI
  - `route-audit-20260713-r4-worst-pair.geojson` — peor par por IoU de R1 (rutas 4 y 15)
  - `route-audit-20260713-r2-worst-pair.geojson` — peor par por IoU de R2 (rutas 4 y 8)

## a. Entorno y reproducción

Idéntico a `profiling-20260711.md` §a y `route-quality-20260712.md` §a:
`docker-compose.prod.yml`, imágenes target `prod`, OSRM real con el PBF completo de
Chile (MLD, perfil foot, `--max-table-size 5000`), PostGIS 15-3.3, Redis 7, MacBook
M4 Pro con Docker Desktop. El worktree nace con volúmenes vacíos: los datasets se
recrearon y el primer `/table` de OSRM se pagó en frío (177.4 s en R1; el resto de
las corridas usó la cache de matriz).

Levantar el stack:

```bash
docker compose -f docker-compose.prod.yml up -d --build db redis osrm backend
```

Recrear los datasets (mismo code path que `POST /api/datasets/from-legacy-selection/`):

```bash
docker compose -f docker-compose.prod.yml run --rm backend python manage.py shell -c "
from apps.datasets import legacy
rows = legacy.list_trees()
loaded = legacy.load_selection([(r['source'], r['external_id']) for r in rows])
full = legacy.create_dataset('Route audit - legacy completo (ambas fuentes)', loaded)
print('FULL', full.id, full.total_trees)
area = legacy.import_area(40)
small = legacy.create_dataset(f'Route audit - {area.dataset_name}', area.trees)
print('SMALL', small.id, small.total_trees)
"
```

- **Completo** (ambas fuentes legacy, n=1607): `af3ad8fa-08fb-46d8-bd0e-be9491d3dedd`
- **Área legacy 40** (n=157): `655bcedf-b382-477c-bf1e-771ac19e0ccd`
- **Disperso sintético** (n=40, uniforme sobre Santiago): `add84a64-f2ad-41a6-a5fc-b4d6f7f1cd3b`, creado con

  ```bash
  docker compose -f docker-compose.prod.yml run --rm backend python manage.py seed_demo \
    --trees 40 --seed 42 --distribution uniform \
    --name "Route audit - seed_demo disperso n40" --no-optimize
  ```

Las cuatro corridas (comando nuevo `route_audit`, una semilla cada una — esto es una
radiografía, no estadística; sobre un dataset real la semilla solo etiqueta la
repetición):

```bash
# R1 — referencia §3.1.1: spatial_term, service 120 s, T_min 7200 s, T_max 10800 s, 120 s de solver
docker compose -f docker-compose.prod.yml run --rm -e PYTHONUNBUFFERED=1 backend \
  python manage.py route_audit \
    --dataset af3ad8fa-08fb-46d8-bd0e-be9491d3dedd --strategy spatial_term \
    --service-time 120 --t-min 7200 --t-max 10800 --time-limit 120 --seed 42 \
    --csv /results/route-audit-20260713-r1.csv \
    --geojson /results/route-audit-20260713-r1.geojson \
    --worst-pair-geojson /results/route-audit-20260713-r4-worst-pair.geojson

# R2 — mismo config con global
docker compose -f docker-compose.prod.yml run --rm -e PYTHONUNBUFFERED=1 backend \
  python manage.py route_audit \
    --dataset af3ad8fa-08fb-46d8-bd0e-be9491d3dedd --strategy global \
    --service-time 120 --t-min 7200 --t-max 10800 --time-limit 120 --seed 42 \
    --csv /results/route-audit-20260713-r2.csv \
    --geojson /results/route-audit-20260713-r2.geojson \
    --worst-pair-geojson /results/route-audit-20260713-r2-worst-pair.geojson

# R3 — área legacy n=157 con defaults de UI (service 300 s, T_min 7200 s, T_max 10800 s)
docker compose -f docker-compose.prod.yml run --rm -e PYTHONUNBUFFERED=1 backend \
  python manage.py route_audit \
    --dataset 655bcedf-b382-477c-bf1e-771ac19e0ccd --strategy spatial_term \
    --service-time 300 --t-min 7200 --t-max 10800 --time-limit 120 --seed 42 \
    --csv /results/route-audit-20260713-r3.csv \
    --geojson /results/route-audit-20260713-r3.geojson

# R3b — disperso n=40 con defaults de UI
docker compose -f docker-compose.prod.yml run --rm -e PYTHONUNBUFFERED=1 backend \
  python manage.py route_audit \
    --dataset add84a64-f2ad-41a6-a5fc-b4d6f7f1cd3b --strategy spatial_term \
    --service-time 300 --t-min 7200 --t-max 10800 --time-limit 120 --seed 42 \
    --csv /results/route-audit-20260713-r3b.csv \
    --geojson /results/route-audit-20260713-r3b.geojson
```

Los artefactos salen a `/results` (bind-mount de `.local/experiments`) y se copiaron
a `docs/experiments/`. Dos ediciones posteriores, ambas de la revisión del PR y ambas
recomputadas sobre las MISMAS filas por ruta emitidas por la corrida (sin volver a
resolver): (1) la columna `self_crossings` de R1 y R2 se recalculó con la métrica ya
corregida — la primera versión contaba como cruce el toque de dos aristas en una parada
compartida, y el dataset legacy tiene árboles con coordenada idéntica —, con lo que R1
pasa de 84 a 83 cruces y R2 de 113 a 111; (2) la `duración` de la fila `resumen` pasó de
media a suma, para que en esa fila también valga duración = servicio + caminata. Las
duraciones medias por corrida siguen en la tabla de §b (T̄). Ninguna otra columna, ni la
geometría, ni las métricas de `RoutingSolution` cambian, y los CSV versionados son ahora
exactamente lo que el comando emite hoy para estas soluciones.

Definiciones: `duración` = `total_estimated_time_sec` de la ruta (entero, `ceil`);
`caminata` = `travel_time_sec` de la ruta; `servicio` = duración − caminata
(= n_árboles × service_time); `walk_ratio` = caminata / duración;
`shortfall` = max(0, T_min − duración); `saturación` = duración / T_max;
`cruces` = pares de aristas NO adyacentes de la secuencia de paradas que se cruzan
propiamente (proyección equirectangular local); dos aristas que solo se tocan en una
parada compartida no cuentan.
La fila `resumen` de cada CSV suma las columnas de conteo y de tiempo, promedia la
saturación, y agrega walk_ratio como caminata_total / duración_total.

## b. Resultados por corrida

| corrida | dataset | estr. | st [s] | k | travel [s] | T̄ [s] | σ(T) [s] | walk medio | walk peor | shortfall total | sat. media | cruces | IoU peor par | drops | >T_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | n=1607 | spatial_term | 120 | 25 | 58664 | 10061 | 526 | 0.234 | 0.885 | 0 | 0.932 | 83 | 0.30 | 0 | 0 |
| R2 | n=1607 | global | 120 | 25 | 60460 | 10132 | 516 | 0.240 | 0.708 | 0 | 0.938 | 111 | 0.58 | 0 | 0 |
| R3 | n=157 | spatial_term | 300 | 6 | 4742 | 8641 | 340 | 0.091 | 0.192 | 0 | 0.800 | 0 | 0.15 | 0 | 0 |
| R3b | n=40 | spatial_term | 300 | 5 | 24391 | 7279 | 79 | 0.671 | 0.750 | 0 | 0.674 | 0 | 0.11 | 0 | 0 |

(`travel`, `T̄`, `σ`, `IoU` desde `RoutingSolution`; el resto desde los CSV por ruta.
`walk medio` = media simple de los walk_ratio por ruta; la fila resumen del CSV usa
el agregado ponderado, ligeramente distinto: 0.233 en R1, 0.239 en R2.)

**R1 reproduce la referencia publicada** (`20260713-real-case-metrics-spatial.csv`,
semilla 42): k=25 = 25 ✓, 0 drops ✓, 0 excesos de T_max ✓, σ 526 vs 519, T̄ 10061 vs
10111, balance 0.842 vs 0.839. El travel total queda en 58664 s vs 59911 s (−2.1 %):
dentro de la variación por corte de wall-clock del GLS documentada en `route-quality-20260712.md` §d, y en la
dirección buena. Las métricas de forma sí dispersan entre repeticiones, como ya
advertía `route-quality-20260712.md` §c: IoU del peor par 0.30 vs 0.46, solapamiento/ruta 91.9 vs 120.2. **No
se contradice ninguna cifra publicada**; k, drops y excesos —los invariantes— coinciden.

Nota de determinismo: R2 se corrió dos veces (la segunda para emitir el GeoJSON del
peor par) con parámetros idénticos y cache caliente, y produjo métricas idénticas
hasta el último dígito. La varianza entre R1 y la referencia proviene del entorno de
la corrida original (matriz fría en la misma corrida), no del comando.

### Tablas por ruta

#### R1 — spatial_term, n=1607

| ruta | n | dur [s] | servicio [s] | caminata [s] | walk_ratio | shortfall [s] | saturación | cruces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 9 | 9396 | 1080 | 8316 | 0.885 | 0 | 0.87 | 0 |
| 2 | 47 | 9489 | 5640 | 3849 | 0.406 | 0 | 0.879 | 6 |
| 3 | 67 | 10354 | 8040 | 2314 | 0.223 | 0 | 0.959 | 6 |
| 4 | 63 | 10709 | 7560 | 3149 | 0.294 | 0 | 0.992 | 3 |
| 5 | 57 | 10670 | 6840 | 3830 | 0.359 | 0 | 0.988 | 6 |
| 6 | 64 | 10620 | 7680 | 2940 | 0.277 | 0 | 0.983 | 3 |
| 7 | 55 | 9262 | 6600 | 2662 | 0.287 | 0 | 0.858 | 2 |
| 8 | 72 | 10658 | 8640 | 2018 | 0.189 | 0 | 0.987 | 3 |
| 9 | 66 | 10607 | 7920 | 2687 | 0.253 | 0 | 0.982 | 2 |
| 10 | 68 | 10659 | 8160 | 2499 | 0.234 | 0 | 0.987 | 6 |
| 11 | 59 | 9038 | 7080 | 1958 | 0.217 | 0 | 0.837 | 1 |
| 12 | 71 | 9705 | 8520 | 1185 | 0.122 | 0 | 0.899 | 2 |
| 13 | 75 | 10492 | 9000 | 1492 | 0.142 | 0 | 0.971 | 3 |
| 14 | 72 | 10036 | 8640 | 1396 | 0.139 | 0 | 0.929 | 1 |
| 15 | 61 | 10730 | 7320 | 3410 | 0.318 | 0 | 0.994 | 1 |
| 16 | 71 | 10136 | 8520 | 1616 | 0.159 | 0 | 0.939 | 1 |
| 17 | 71 | 9841 | 8520 | 1321 | 0.134 | 0 | 0.911 | 1 |
| 18 | 70 | 9734 | 8400 | 1334 | 0.137 | 0 | 0.901 | 2 |
| 19 | 73 | 10077 | 8760 | 1317 | 0.131 | 0 | 0.933 | 13 |
| 20 | 73 | 10254 | 8760 | 1494 | 0.146 | 0 | 0.949 | 1 |
| 21 | 66 | 9760 | 7920 | 1840 | 0.189 | 0 | 0.904 | 7 |
| 22 | 68 | 9373 | 8160 | 1213 | 0.129 | 0 | 0.868 | 6 |
| 23 | 73 | 10447 | 8760 | 1687 | 0.161 | 0 | 0.967 | 1 |
| 24 | 64 | 9307 | 7680 | 1627 | 0.175 | 0 | 0.862 | 4 |
| 25 | 72 | 10163 | 8640 | 1523 | 0.15 | 0 | 0.941 | 2 |
| **resumen** | 1607 | 251517 | 192840 | 58677 | 0.233 | 0 | 0.932 | 83 |

#### R2 — global, n=1607

| ruta | n | dur [s] | servicio [s] | caminata [s] | walk_ratio | shortfall [s] | saturación | cruces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 25 | 10264 | 3000 | 7264 | 0.708 | 0 | 0.95 | 3 |
| 2 | 37 | 9018 | 4440 | 4578 | 0.508 | 0 | 0.835 | 2 |
| 3 | 66 | 10192 | 7920 | 2272 | 0.223 | 0 | 0.944 | 12 |
| 4 | 62 | 9706 | 7440 | 2266 | 0.233 | 0 | 0.899 | 4 |
| 5 | 58 | 9445 | 6960 | 2485 | 0.263 | 0 | 0.875 | 3 |
| 6 | 65 | 10751 | 7800 | 2951 | 0.274 | 0 | 0.995 | 9 |
| 7 | 58 | 10542 | 6960 | 3582 | 0.34 | 0 | 0.976 | 4 |
| 8 | 57 | 9879 | 6840 | 3039 | 0.308 | 0 | 0.915 | 1 |
| 9 | 63 | 9480 | 7560 | 1920 | 0.203 | 0 | 0.878 | 5 |
| 10 | 66 | 9480 | 7920 | 1560 | 0.165 | 0 | 0.878 | 5 |
| 11 | 64 | 9573 | 7680 | 1893 | 0.198 | 0 | 0.886 | 3 |
| 12 | 76 | 10716 | 9120 | 1596 | 0.149 | 0 | 0.992 | 8 |
| 13 | 66 | 10589 | 7920 | 2669 | 0.252 | 0 | 0.98 | 5 |
| 14 | 66 | 9207 | 7920 | 1287 | 0.14 | 0 | 0.853 | 0 |
| 15 | 69 | 9947 | 8280 | 1667 | 0.168 | 0 | 0.921 | 10 |
| 16 | 72 | 10603 | 8640 | 1963 | 0.185 | 0 | 0.982 | 3 |
| 17 | 76 | 10154 | 9120 | 1034 | 0.102 | 0 | 0.94 | 2 |
| 18 | 62 | 10635 | 7440 | 3195 | 0.3 | 0 | 0.985 | 1 |
| 19 | 72 | 10546 | 8640 | 1906 | 0.181 | 0 | 0.976 | 11 |
| 20 | 76 | 10445 | 9120 | 1325 | 0.127 | 0 | 0.967 | 2 |
| 21 | 74 | 10460 | 8880 | 1580 | 0.151 | 0 | 0.969 | 1 |
| 22 | 77 | 10575 | 9240 | 1335 | 0.126 | 0 | 0.979 | 7 |
| 23 | 75 | 10434 | 9000 | 1434 | 0.137 | 0 | 0.966 | 5 |
| 24 | 49 | 9939 | 5880 | 4059 | 0.408 | 0 | 0.92 | 2 |
| 25 | 76 | 10730 | 9120 | 1610 | 0.15 | 0 | 0.994 | 3 |
| **resumen** | 1607 | 253310 | 192840 | 60470 | 0.239 | 0 | 0.938 | 111 |

#### R3 — área legacy 40, n=157, defaults de UI

| ruta | n | dur [s] | servicio [s] | caminata [s] | walk_ratio | shortfall [s] | saturación | cruces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 26 | 8036 | 7800 | 236 | 0.029 | 0 | 0.744 | 0 |
| 2 | 28 | 8945 | 8400 | 545 | 0.061 | 0 | 0.828 | 0 |
| 3 | 24 | 8908 | 7200 | 1708 | 0.192 | 0 | 0.825 | 0 |
| 4 | 28 | 8615 | 8400 | 215 | 0.025 | 0 | 0.798 | 0 |
| 5 | 27 | 8956 | 8100 | 856 | 0.096 | 0 | 0.829 | 0 |
| 6 | 24 | 8385 | 7200 | 1185 | 0.141 | 0 | 0.776 | 0 |
| **resumen** | 157 | 51845 | 47100 | 4745 | 0.092 | 0 | 0.8 | 0 |

#### R3b — seed_demo disperso, n=40, defaults de UI

| ruta | n | dur [s] | servicio [s] | caminata [s] | walk_ratio | shortfall [s] | saturación | cruces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7 | 7315 | 2100 | 5215 | 0.713 | 0 | 0.677 | 0 |
| 2 | 10 | 7419 | 3000 | 4419 | 0.596 | 0 | 0.687 | 0 |
| 3 | 8 | 7222 | 2400 | 4822 | 0.668 | 0 | 0.669 | 0 |
| 4 | 9 | 7229 | 2700 | 4529 | 0.627 | 0 | 0.669 | 0 |
| 5 | 6 | 7209 | 1800 | 5409 | 0.75 | 0 | 0.667 | 0 |
| **resumen** | 40 | 36394 | 12000 | 24394 | 0.67 | 0 | 0.674 | 0 |

## c. Veredicto sobre la hipótesis, sub-afirmación por sub-afirmación

**Afirmación 1 — "quedar corto de T_min se arregla caminando": CONFIRMADA en régimen
disperso, con la evidencia más nítida de todo el experimento.**

En R3b las 5 rutas tienen servicio < T_min y la caminata cubre el hueco **casi
exactamente**:

| ruta | servicio [s] | hueco a T_min [s] | caminata [s] | cobertura del hueco | duración [s] |
| --- | --- | --- | --- | --- | --- |
| 1 | 2100 | 5100 | 5215 | 102.3 % | 7315 |
| 2 | 3000 | 4200 | 4419 | 105.2 % | 7419 |
| 3 | 2400 | 4800 | 4822 | 100.5 % | 7222 |
| 4 | 2700 | 4500 | 4529 | 100.6 % | 7229 |
| 5 | 1800 | 5400 | 5409 | 100.2 % | 7209 |

Las cinco rutas caminan lo justo para tocar T_min (100.2–105.2 % del hueco) y ahí se
detienen: saturación 0.67 (≈ T_min/T_max), σ(T) = 79 s, shortfall 0. El censo son
12 000 s; la caminata, 24 391 s — **dos veces más caminata que censo**. Esto reproduce
exactamente la queja humana.

En R1 la firma aparece en la ruta 1: 9 árboles, 1080 s de censo y **8316 s caminando**
(walk_ratio 0.885); su hueco a T_min es 6120 s y camina el 136 % de ese hueco. Otras
5 rutas de R1 y 6 de R2 tienen servicio < T_min, pero caminan mucho más que su hueco
(247–1632 %): ahí la caminata no es relleno, es geometría (rutas grandes y dispersas
que además llegan cerca de T_max).

**Afirmación 2 — "el soft upper empuja todo hacia el punto medio [T_min, midpoint]":
REFUTADA tal como está escrita.** Con los defaults, midpoint = 9000 s. En R1 **las 25
rutas terminan POR ENCIMA del midpoint** (9038–10730 s, T̄ 10061, saturación media
0.932, mínima 0.837); en R2, idéntico (25/25, T̄ 10132). Es decir: la penalización de
500/s sobre el midpoint **se paga en todas las rutas** y no logra bajar las duraciones
a la banda. El atractor observado no es el punto medio:

- con servicio abundante (n=1607): las duraciones se pegan a **T_max** (saturación
  0.93–0.94, máximo 0.994, sin excederlo nunca);
- con servicio escaso (n=40 disperso): se pegan a **T_min** (saturación 0.674).

Consecuencia práctica para el experimento de sensibilidad a penalizaciones
(`penalty-sensitivity-20260713.md`): el término que realmente ordena las duraciones no es
el soft upper en el midpoint, sino la combinación T_min (desde abajo) + T_max/tamaño
de flota (desde arriba). Observación adicional **no medida** (hipótesis para ese
experimento, no afirmación): bajo la función objetivo actual, 25 rutas pagando ~1060 s de exceso sobre
el midpoint cuestan ~13 M en penalización, mientras que abrir vehículos adicionales
cuesta 100 k cada uno; que el solver no llegue a esa configuración sugiere que el GLS
no la alcanza en 120 s (las cuatro corridas agotaron el presupuesto: `solve.total` =
120.0 s) o que el término de travel lo compensa. No lo aíslo aquí.

**Afirmación 3 — "minimizar desplazamiento queda como desempate": consistente con los datos.**
spatial_term y global entregan k idéntico (25), travel dentro del 3 % (58 664 vs
60 460 s) y walk_ratio agregado casi igual (0.233 vs 0.239), pero difieren fuerte en
forma: solapamiento/ruta 91.9 vs 132.4, cruces 83 vs 111, IoU del peor par 0.30 vs
0.58. Cambiar el término espacial reordena la geometría sin mover las duraciones —
las duraciones las fijan las penalizaciones, no el desplazamiento.

**Afirmación 4 — "el síntoma depende del dataset": CONFIRMADA.** walk_ratio agregado: 0.233
(n=1607, st=2 min) · 0.092 (n=157, defaults de UI) · **0.670** (n=40 disperso,
defaults de UI). El caso patológico candidato inicial (área legacy n=157) **NO es
patológico**: es una zona densa donde 300 s de censo por árbol dominan (walk_ratio
0.09, la mejor de las cuatro corridas). La patología necesita **dispersión**, no
tamaño chico: aparece cuando los árboles están lejos entre sí y el servicio por ruta
no alcanza T_min.

## d. Preclasificación de las rutas sospechosas

Hecha **antes** de mirar cualquier idea de recalibración; alimenta el diseño del
experimento de sensibilidad a penalizaciones (`penalty-sensitivity-20260713.md`).

**(a) Relleno por T_min — 8 rutas.** Criterio: servicio < T_min y caminata ≈ el hueco
(100–150 %).

| ruta | evidencia (una línea) |
| --- | --- |
| R3b 1–5 (las 5) | caminata cubre 100.2–105.2 % del hueco a T_min y la duración se detiene en 7209–7419 s (T_min = 7200) |
| R1 ruta 1 | 9 árboles: 1080 s de censo, 8316 s de caminata (walk 0.885), 136 % del hueco |
| R2 ruta 1 | 25 árboles: 3000 s de censo, 7264 s de caminata (walk 0.708), 173 % del hueco |
| R2 ruta 2 | 37 árboles: 4440 s de censo, 4578 s de caminata (walk 0.508), 166 % del hueco |

**(b) Solapamiento entre rutas vecinas — 2 pares (mapas dedicados).**

| par | evidencia |
| --- | --- |
| R2 rutas 4 y 8 (global) | IoU de bbox 0.576, el peor par de las cuatro corridas → `route-audit-20260713-r2-worst-pair.geojson` |
| R1 rutas 4 y 15 (spatial_term) | IoU 0.303, peor par de la referencia → `route-audit-20260713-r4-worst-pair.geojson` |

A nivel de corrida, global solapa 44 % más por ruta que spatial_term (132.4 vs 91.9
puntos ajenos dentro del bbox), consistente con `route-quality-20260712.md` (global
solapa más por ruta que spatial_term).

**(c) Secuencia intra-ruta subóptima (corte por wall-clock del GLS) — 13 rutas** con
≥6 auto-cruces del polyline (7 en R1, 6 en R2), lideradas por:

| ruta | evidencia |
| --- | --- |
| R1 ruta 19 | 13 cruces con walk_ratio 0.131 — la ruta es compacta, lo que se cruza es el ORDEN de visita |
| R2 ruta 3 | 12 cruces, walk 0.223 |
| R2 ruta 19 | 11 cruces, walk 0.181 |
| R2 ruta 15 | 10 cruces, walk 0.168 |
| R1 rutas 2, 3, 5, 10, 21, 22 · R2 rutas 6, 12, 22 | 6–9 cruces cada una |
| R3 y R3b | 0 cruces en las 11 rutas: en instancias chicas el GLS sí converge |

Las cuatro corridas consumieron el presupuesto completo (`solve.total` = 120.0 s), o
sea que el GLS nunca convergió en n=1607: los cruces son coherentes con una secuencia
no terminada de optimizar, no con la función objetivo.

**(d) Artefacto de la matriz OSRM (perfil foot) — 40 arcos de 1429 (2.8 %), ninguna
ruta dominada por él.** Medido sobre la solución de R1 comparando el tiempo OSRM de
cada arco consecutivo contra la distancia haversine a 1.39 m/s (5 km/h):

- factor de desvío: mediana **1.00**, p90 1.59, p99 4.81, máximo 11.5;
- 40 arcos con factor > 3 (14 con factor > 5), que acumulan 2666 s = **4.5 % del travel
  total** de R1;
- los peores son arcos CORTOS: R5 secuencia 1 (26 m en línea recta → 212 s de camino),
  R9.41 (10 m → 79 s), R11.51 (19 m → 129 s) — patrón típico de dos árboles a lados
  opuestos de una barrera (bandejón, reja, muro) que el perfil foot debe rodear;
- mediana del factor por ruta: 0.95–1.15 en las 25 rutas → ninguna ruta es "artefacto
  OSRM" en su conjunto.

Comando de la medición:

```bash
docker compose -f docker-compose.prod.yml run --rm backend python manage.py shell -c "
from statistics import median, mean
from apps.datasets.models import Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.models import RoutingSolution
from apps.optimization.route_metrics import haversine
sol = RoutingSolution.objects.filter(strategy='spatial_term', job__config__service_time_sec=120).order_by('-generated_at').first()
trees = sorted(Tree.objects.filter(dataset=sol.job.config.dataset, is_active=True), key=lambda t: t.id)
idx = {t.id: i for i, t in enumerate(trees)}
m = OSRMCostMatrixBuilder().get_cached(trees)
factors = []
for route in sol.routes.all():
    stops = list(route.stops.select_related('tree').order_by('sequence'))
    for a, b in zip(stops[:-1], stops[1:]):
        d = haversine((a.tree.location.y, a.tree.location.x), (b.tree.location.y, b.tree.location.x))
        if d >= 5:
            factors.append(m[idx[a.tree_id]][idx[b.tree_id]] / (d / 1.39))
print(len(factors), round(median(factors), 2), round(mean(factors), 2), sum(1 for f in factors if f > 3))
"
```

**Resumen de la clasificación:** (a) 8 rutas · (b) 2 pares · (c) 13 rutas · (d) 40
arcos, 0 rutas. Las clases no son excluyentes (una ruta con relleno por T_min puede
además cruzarse consigo misma), pero el peso está claro: **la caminata excesiva es (a)
en el régimen disperso y geometría legítima en el denso; los "vueltas sin sentido" que
se ven en el mapa del caso real son mayormente (c)**, y (d) es real pero marginal
(≤4.5 % del travel).

## e. Preguntas abiertas para la revisión visual (Alberto sobre los GeoJSON)

1. **R1 ruta 1 y R2 rutas 1–2** (`r1.geojson`, `r2.geojson`): ¿son rutas "de relleno"
   en la periferia (árboles sueltos lejos del núcleo) o atraviesan zonas ya cubiertas
   por otras rutas? Si es lo segundo, es (a)+(b) y el experimento de sensibilidad a
   penalizaciones debería atacar la penalización;
   si es lo primero, es geometría del dataset y va a limitaciones.
2. **Peor par de global (R2 rutas 4 y 8, IoU 0.576)** vs **peor par de spatial_term
   (R1 rutas 4 y 15, IoU 0.303)**: ¿entrelazado real (dos rutas mezcladas calle a
   calle) o dos rutas contiguas en una frontera densa cuyos bbox se pisan sin que las
   paradas se mezclen? El IoU es de cajas, no de trayectos: solo el mapa lo distingue.
3. **R1 ruta 19 (13 cruces, walk 0.131)**: ¿los cruces son "vueltas" evidentes a ojo o
   son cruces inocuos entre calles paralelas? Esto calibra si el indicador de cruces
   sirve como proxy de la queja "vueltas innecesarias" o hay que descartarlo.
4. **R3 (n=157, walk 0.09)**: ¿esas rutas se ven bien? Si el ojo humano igual las
   critica, la queja no es sobre caminata y hay una quinta causa que este experimento
   no captura.
5. **R3b (disperso, walk 0.67)**: ¿la caminata se ve como "recorrer la ciudad" (dataset
   imposible) o como "vueltas sobre el mismo barrio" (relleno artificial)? Es la
   diferencia entre documentar la limitación y recalibrar en el experimento de
   sensibilidad a penalizaciones.
6. Arcos de factor > 5 (14 en R1, p. ej. R5 parada 1: 26 m → 212 s): ¿corresponden a
   pares de árboles separados por bandejón/reja? Confirmarlo cierra (d) como artefacto
   conocido y acotado.

## f. Qué queda fijado para el experimento de sensibilidad a penalizaciones

- La sensibilidad debe barrer `SOFT_LOWER_PENALTY` (Afirmación 1 confirmada) **y** el objetivo
  del soft upper (Afirmación 2 refutada: hoy no cumple ninguna función salvo pagar penalización
  en todas las rutas), midiendo walk_ratio y cobertura del hueco de T_min además de las
  métricas agregadas.
- El caso patológico de ese experimento debe ser el **disperso** (n=40, `add84a64-…`), no el área
  n=157: es el único que reproduce "más caminata que censo".
- La referencia n=1607 es reproducible desde este comando y no contradice §3.1.1; la
  comparación de ese experimento contra ella es válida.
- Si ese experimento no encuentra variante ganadora, el material honesto para §3.1.4 ya está aquí:
  el solver optimiza duración objetivo, no desplazamiento, y eso es visible en 25/25
  rutas de la referencia.
