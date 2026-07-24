# ¿Predice la geometría de la instancia qué configuración gana? — re-juicio por régimen

**Fecha:** 2026-07-24
**Estado al commitear esta sección:** pre-registro. Motivación, features, predicados, definición
de ganador, criterio y falsadores se commitean **antes** de ejecutar una sola línea de análisis.
Los resultados se agregan después, sin tocar nada de lo anterior; cualquier desviación se declara
como tal.

**Este ciclo no corre el solver.** No hay resoluciones nuevas, no hay CPU de OR-Tools, no hay
llamadas OSRM nuevas. Es un re-juicio de CSVs ya versionados más features geométricas calculables
sin resolver. Tampoco toca ningún default de producción: su salida esperada es una sección de
discusión / trabajo futuro, no un cambio en `solver.py`.

---

## 1. Motivación

La serie lleva trece ciclos de barridos buscando una **configuración ganadora global** del VRP y no
la ha encontrado. Pero tres ciclos independientes reportaron, cada uno por su cuenta, que el
ganador es **regional**:

- `route-config-algorithm-sweep-20260718.md` cerró con "hace falta un guard de régimen, no una
  sola configuración": `upper-tmax-tmin9000` mata auto-cruces en `n=1607` pero paddea áreas ralas.
- `floor-price-upper-target-20260723.md` midió `upper@T_max` con el piso default sobre las 12
  instancias congeladas: el relleno cae **−96 %** en `area-27`, **−25 %** en `area-26` y
  **−0,6 %** en `area-29`. La misma celda, tres resultados incompatibles.
- `sweep-metrology-20260720.md` y `stops-penalty-sweep-20260722.md` establecieron que el relleno de
  `area-26-n157` es **geometría irreducible** (k=3 es el mínimo factible): la instancia decide qué
  es alcanzable **antes** de que se elija configuración.

El mecanismo que explica el tercer punto ya está diagnosticado y escrito en
`.claude/rules/ortools-vrp.md` ("Marginal price, not nominal weight"): por debajo del piso blando
`T_min` el solver está **pagado** a −9 999 s⁻¹ por caminar. Si el trabajo total de la instancia no
alcanza para llenar `k · T_min` con las rutas que la capacidad dura `T_max` obliga a abrir,
**rellenar es el óptimo del modelo**, no un defecto de la búsqueda. Ninguna configuración que mueva
el **techo** puede arreglar eso, porque el techo no es lo que está cobrando.

Ese mecanismo es calculable **antes de resolver**: `T_min`, `T_max`, el tiempo de servicio y una
cota inferior de viaje (`MSF_k`, ya publicada en `sweep-metrology-20260720-decomposition.csv`) son
todos anteriores al solver.

**Hipótesis del ciclo:** existe un predicado calculable antes de resolver, definido solo con
geometría de la instancia y parámetros del modelo, que predice qué celda gana en esa instancia. Si
existe, el resultado acumulado de trece ciclos deja de ser "no hay configuración ganadora" y pasa a
ser "**el ganador depende del régimen, y el régimen es predecible**".

### Exposición previa a los resultados — declarada por adelantado

Honestidad obligatoria: al escribir este pre-registro **ya están publicados** los reportes de los
ciclos anteriores, incluidos los tres números de `area-26/27/29` citados arriba. No se puede
afirmar ceguera respecto de ellos. Lo que sí se afirma, y es lo que hace falsable al ciclo, es que:

1. el predicado sale del **mecanismo** (piso infactible ⟹ relleno pagado), documentado en la regla
   de OR-Tools y diagnosticado por `tmin`-padding en ciclos previos, **no** de mirar qué celda ganó;
2. el predicado se define **sobre las 12 instancias**, no solo sobre las 3 áreas cuyos números se
   conocen: 9 de las 12 instancias (las `battery-*` y `reference-n1607`) entran a ciegas respecto de
   su clasificación;
3. **no** se han leído todavía los ganadores por instancia bajo el criterio lexicográfico de la
   §4 — ese cruce es exactamente lo que este ciclo va a producir, y nunca se produjo antes;
4. se registra **cuántos predicados se prueban** (dos, §3) y se reportan **los dos**, gane o pierda
   cada uno. Si al ejecutar el análisis se probara alguno más, se declara explícitamente como
   post-hoc y baja el tono de la conclusión.

### No hay holdout y no se pretende que lo haya

Con **n = 12 instancias** no existe partición train/test que signifique algo: cualquier "holdout"
de 3 instancias tiene un error de estimación mayor que el efecto que mediría. Este ciclo, por
diseño, **no ajusta un clasificador**. Publica una **regla mecanicista verificada**: un umbral
derivado de la estructura de precios del objetivo (no estimado de los datos) y la cuenta de en
cuántas instancias acierta. Cualquier lectura de "modelo entrenado", "precisión" o "generalización"
sobre este resultado es una sobre-lectura, y el reporte lo dirá en su veredicto.

---

## 2. Features por instancia (todas calculables antes de resolver)

Se computan sobre las 12 instancias congeladas de `docs/experiments/instances/`
(`battery-n{50,100,200,400,800,1000}`, `battery-sparse-n{250,500}`,
`area-{26-n157,27-n72,29-n43}`, `reference-n1607`). **La suite no se toca**: se lee, no se edita.

Parámetros del censo, fijos: servicio 120 s/árbol, `T_min` = 7 200 s, `T_max` = 10 800 s.

**Geométricas puras** (solo `lat`/`lon` de los CSV de instancia, proyección equirectangular local
alrededor del centroide):

| feature | definición |
| --- | --- |
| `n` | número de árboles |
| `bbox_area_km2` | área de la caja envolvente en la proyección local |
| `density_per_km2` | `n / bbox_area_km2` |
| `diameter_m` | máxima distancia par-a-par (euclídea proyectada) |
| `extent_major_m` | extensión longitudinal: rango de la proyección sobre el 1er eje principal |
| `extent_minor_m` | rango sobre el 2º eje principal |
| `elongation` | `extent_major / extent_minor` |

**Derivadas del modelo, reusando cotas ya publicadas** (de
`sweep-metrology-20260720-decomposition.csv`; `MSF_k` y `nn_mean` provienen de la matriz OSRM
cacheada y **no se recomputan**):

| feature | definición |
| --- | --- |
| `service_total_sec` | `n · 120` |
| `nn_mean_sec` | viaje medio al vecino más cercano (OSRM) |
| `msf_k_sec` | cota inferior de viaje del bosque de expansión mínima con `k` componentes |
| `k_hat` | **flota mínima factible**: menor `k` con `service_total + MSF_k ≤ k · T_max` |
| `work_lb_sec` | `service_total + MSF_{k_hat}` — trabajo total mínimo de la instancia |
| `saturation_hat` | `work_lb / (k_hat · T_max)` ∈ (0, 1] — qué tan llenas quedan las rutas |
| `rho_pad` | **`k_hat · T_min / work_lb`** — el predicado de relleno |

`k_hat` usa `MSF_k` como cota inferior de viaje, así que es una cota inferior de la flota: ninguna
solución sin drops puede usar menos rutas. Es exactamente la cantidad que
`sweep-metrology-20260720.md` llamó "k=3 es el mínimo factible" para `area-26`.

---

## 3. Predicados candidatos — **se prueban dos, se reportan los dos**

### H1 — predicado de relleno (mecanicista)

> **`rho_pad = k_hat · T_min / work_lb > 1`** ⟹ la instancia está en **régimen de relleno
> forzado**: el piso blando es infactible a la flota mínima, el modelo paga por caminar, y
> **ninguna** celda del factorial reduce el relleno de forma material.

Predicción operativa, con umbral heredado del criterio de la serie:

- **H1a.** En toda instancia con `rho_pad > 1`, **ninguna** celda baja `relleno_msf_sec` un ≥ 30 %
  respecto del control `floor10000-mid`.
- **H1b.** En toda instancia con `rho_pad ≤ 1`, **alguna** celda baja `relleno_msf_sec` un ≥ 30 %.

`T_min` y `T_max` no se ajustan a los datos: son los parámetros de producción. El umbral `1` no es
un hiperparámetro: es el punto exacto donde el piso deja de ser satisfacible, o sea donde el precio
marginal del relleno cambia de signo.

### H2 — guard de régimen (asignación régimen → configuración)

> El ganador por instancia bajo el criterio de la §4 se predice por el régimen:
> **`rho_pad ≤ 1` ⟹ gana un brazo `*-tmax`**; **`rho_pad > 1` ⟹ gana el control
> `floor10000-mid`**.

Mecanismo: subir el techo a `T_max` solo puede comprar algo cuando existe holgura entre el piso y
la capacidad — es decir, cuando el piso ya es satisfacible. En régimen de relleno forzado, mover el
techo no toca el término que está pagando, y lo único que queda de ese movimiento es su costo
(balance peor, rutas degeneradas), así que el control debería ganar.

### Comparación obligatoria contra la clase mayoritaria

Un predicado que acierta 10/12 **no vale nada** si el ganador es el mismo en 10 de las 12
instancias: ahí "predice siempre lo mismo" acierta igual. Por eso el reporte publica, lado a lado:

- aciertos del predicado (H2), y
- aciertos de la **regla trivial** "gana siempre la celda que más veces gana" (clase mayoritaria).

**El predicado solo se declara informativo si supera estrictamente a la clase mayoritaria.**

---

## 4. Definición EXACTA de "ganador" por instancia — fijada antes de mirar

Fuente primaria: `floor-price-upper-target-20260723.csv` (288 filas = 8 celdas × 12 instancias × 3
semillas). Es el CSV más limpio y el único con `crossings_chord`, `crossings_road` y
`relleno_msf_sec` en la misma corrida.

**Todas las comparaciones son intra-CSV.** No se compara la media de un brazo con la media
publicada por otro ciclo: el travel de un mismo brazo se movió 59 971 → 62 751 s entre ciclos, un
salto mayor que su desviación entre semillas. Los otros CSVs listados en la §6 se usan solo como
**contexto cualitativo**, y toda lectura que los cruce se marca como tal en el texto.

Por instancia, cada celda se agrega como **media sobre sus 3 semillas** y su **σ poblacional**.

**Puertas eliminatorias** (una celda que falla cualquiera queda fuera de la carrera de esa
instancia):

1. `drops` = 0 en las 3 semillas.
2. `degenerate_routes` = 0 en las 3 semillas (una ruta es degenerada con < 5 paradas **o**
   < 1 800 s; la columna ya lo codifica).
3. `balance` ≥ 0,60 en media.

**Orden lexicográfico entre las celdas que pasan las puertas** (menor es mejor en las tres):

4. `relleno_msf_sec`
5. `crossings_road`
6. `travel_sec`

**Regla de empate:** una diferencia de media menor o igual a la mayor de las dos σ **no es una
diferencia** (regla explícita de `.claude/rules/experiment-metrics.md`); se pasa a la métrica
siguiente. Si tras las tres métricas persiste el empate, **gana el control** `floor10000-mid` — el
desempate conservador, porque un cambio de configuración que no se distingue del control no compra
nada.

### Justificación de cada elección

- **Las puertas van primero** porque son las condiciones de operación, no preferencias: una ruta
  con drops deja árboles sin censar, y una ruta degenerada (3 paradas, 2 h) es inoperable aunque su
  travel sea excelente. Es el orden heredado del criterio de la serie.
- **Balance 0,60** es el piso heredado del criterio vigente, no uno nuevo.
- **`relleno_msf_sec` antes que cruces** porque el relleno es la queja operativa concreta (caminar
  sin censar) y porque `MSF_k` es una cota alcanzable, no un cero imposible.
- **`crossings_road` y no `crossings_chord`.** Desviación declarada y justificada **antes** de
  medir: dos ciclos independientes establecieron que la métrica de cuerdas es un proxy parcial
  (ρ = 0,527 y 0,520) y que **en `reference-n1607` está invertida** respecto de la geometría de
  calle (ρ = −0,575 y −0,618). Juzgar con cuerdas es juzgar con el signo cambiado donde más
  importa. Se reporta `crossings_chord` en toda tabla como contexto, nunca como criterio.
- **`travel` último** porque las celdas del factorial difieren en travel dentro de ±4 %, un margen
  que la serie ya mostró que se mueve más entre corridas que entre celdas.

---

## 5. Las dos lecturas que el reporte debe publicar, con números lado a lado

Obligatorio, gane o pierda el predicado:

- **(a) Mejor default único.** La celda que, aplicada a **las 12 instancias**, maximiza el número
  de instancias donde gana (o donde no pierde), con su costo agregado en relleno, `crossings_road`,
  travel, balance y rutas degeneradas.
- **(b) Guard de régimen.** La política "si `rho_pad > 1` usa el control, si no usa `*-tmax`", con
  los mismos agregados, **y** el número de instancias donde la política elige efectivamente al
  ganador.

Si (b) no supera a (a) en el agregado, se dice así: el guard no compra nada y la conclusión del
ciclo es negativa.

---

## 6. Fuentes de datos

- **Primaria (todo veredicto sale de aquí):** `floor-price-upper-target-20260723.csv`.
- **Features reusadas:** `sweep-metrology-20260720-decomposition.csv` (`MSF_k`, `nn_mean`,
  `service_total`), `docs/experiments/instances/*.csv` (coordenadas).
- **Contexto cualitativo, nunca comparado en media contra la primaria:**
  `crossing-metric-validation-20260723-*.csv`, `sweep-metrology-20260720-rejudge.csv` y
  `-decomposition.csv`, `stops-penalty-sweep-20260722-*.csv`,
  `tsp-achievable-anchor-20260722-rejudge.csv`.

---

## 7. Qué falsaría la hipótesis

Explícito y numérico, escrito antes de mirar:

- **H1 falsada** si existe **una sola** instancia con `rho_pad > 1` donde alguna celda baja el
  relleno ≥ 30 %, **o** una sola instancia con `rho_pad ≤ 1` donde ninguna celda lo logra. El
  predicado se propone como mecanicista y determinista; una excepción lo rompe.
- **H2 falsada** si el régimen acierta el ganador en **≤ 9 de 12** instancias, **o** si no supera
  estrictamente a la regla de clase mayoritaria. Empatar con "gana siempre el control" es fallar.
- **Hipótesis del ciclo falsada** si (b) no mejora a (a) en ninguna de las métricas agregadas del
  §5.

**Si el predicado no predice, ese es el resultado y se publica igual.** Un resultado negativo aquí
cuesta cero CPU y cierra una vía. No se buscará un tercer predicado hasta que alguno acierte: si el
análisis termina probando más de los dos registrados, se reporta el total y se declara post-hoc.

---

## 8. Lo que NO hace este ciclo

- No corre el solver, no re-mide nada, no consume CPU de OR-Tools ni llamadas OSRM nuevas.
- No cambia ningún default de producción, gane o pierda el predicado. Un guard de régimen aprobado
  aquí sería **propuesta verificada + trabajo futuro**, con su propio ciclo de validación por
  delante.
- No ajusta umbrales a los datos: `T_min`, `T_max`, el umbral `rho_pad = 1` y el −30 % de relleno
  vienen de producción y del criterio heredado.
- No toca `docs/experiments/instances/` (suite congelada), ni el post-pass, ni los clusters, ni el
  warm start.
- No adopta `crossings_road` como criterio oficial de la serie: lo usa **en este re-juicio**, con
  la justificación de la §4, y su adopción formal sigue siendo un ciclo aparte.
