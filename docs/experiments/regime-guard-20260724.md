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

---

## Resultados

Datos: `regime-guard-20260724-features.csv` (12 filas, una por instancia),
`regime-guard-20260724-cells.csv` (96 filas = 8 celdas × 12 instancias, medias y σ sobre 3
semillas) y `regime-guard-20260724-winners.csv` (12 filas, el ganador y el predicho por
instancia). Todos derivados de `floor-price-upper-target-20260723.csv` sin resolver nada.

**Desviaciones respecto del pre-registro:** una sola, menor. El §3 registró el guard como
"`rho_pad ≤ 1` ⟹ gana un brazo `*-tmax`"; el brazo concreto elegido para instanciar la política es
`floor10000-tmax` — el `*-tmax` con el precio de piso de producción, el único que no mezcla el
factor A con el B. Los otros tres `*-tmax` son indistinguibles de él en 10 de las 12 instancias.
Nada más se movió: ni umbrales, ni métricas, ni el orden lexicográfico.

### Comprobación del instrumento

`k_hat` reproduce el hecho ya publicado por `sweep-metrology-20260720.md`: **`area-26-n157` tiene
`k_hat` = 3**, exactamente el "k = 3 es el mínimo factible" de aquel ciclo, calculado aquí por un
camino independiente (cota `MSF_k` + capacidad `T_max`). En `reference-n1607` da `k_hat` = 21
contra las 25 rutas que el solver abre: la cota es una cota, y la brecha 21 → 25 es el precio del
piso más la búsqueda, no un error de la cuenta.

### Features pre-solver de las 12 instancias

| instancia | n | densidad (/km²) | diámetro (km) | eje mayor (km) | elongación | `k_hat` | `rho_pad` | `saturation_hat` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `reference-n1607` | 1607 | 22 | 11,88 | 11,78 | 3,14 | 21 | 0,675 | 0,988 |
| `battery-sparse-n500` | 500 | 140 | 2,01 | 1,97 | 1,00 | 7 | 0,684 | 0,974 |
| `battery-n1000` | 1000 | 276 | 2,01 | 2,01 | 1,01 | 13 | 0,690 | 0,966 |
| `battery-sparse-n250` | 250 | 70 | 2,01 | 1,98 | 1,00 | 4 | 0,697 | 0,957 |
| `area-27-n72` | 72 | 172 | 0,98 | 0,97 | 4,54 | 1 | 0,724 | 0,921 |
| `battery-n800` | 800 | 246 | 1,89 | 1,89 | 1,01 | 11 | 0,730 | 0,913 |
| `battery-n200` | 200 | 116 | 1,45 | 1,40 | 1,14 | 3 | 0,752 | 0,887 |
| `battery-n400` | 400 | 169 | 1,61 | 1,60 | 1,02 | 6 | 0,779 | 0,856 |
| `battery-n50` | 50 | 65 | 0,95 | 0,92 | 1,11 | 1 | 0,823 | 0,810 |
| `area-26-n157` | 157 | 130 | 1,35 | 1,34 | 1,68 | 3 | 0,962 | 0,693 |
| `battery-n100` | 100 | 105 | 1,02 | 0,98 | 1,00 | 2 | 0,986 | 0,676 |
| `area-29-n43` | 43 | 493 | 0,42 | 0,39 | 1,72 | 1 | **1,210** | 0,551 |

**Una sola instancia de las 12 cae en régimen de relleno forzado**: `area-29-n43`, con
`rho_pad` = 1,21. `area-26-n157` (0,962) y `battery-n100` (0,986) quedan justo por debajo del
umbral. Que el predicado parta 1/11 ya limita cuánto puede discriminar: una regla que separa una
instancia de once no puede explicar doce ganadores distintos.

### Ganadores por instancia bajo el criterio de la §4

| instancia | `rho_pad` | régimen | ganador medido | predicho por el guard | acierta | mejor caída de relleno | H1 |
| --- | ---: | --- | --- | --- | :-: | ---: | :-: |
| `reference-n1607` | 0,675 | satisfacible | `floor10000-mid` | `floor10000-tmax` | no | 5,5 % | no |
| `battery-sparse-n500` | 0,684 | satisfacible | `floor10000-mid` | `floor10000-tmax` | no | 0,0 % | no |
| `battery-n1000` | 0,690 | satisfacible | `floor10000-mid` | `floor10000-tmax` | no | 0,7 % | no |
| `battery-sparse-n250` | 0,697 | satisfacible | `floor100-tmax` | `floor10000-tmax` | no | 10,6 % | no |
| `area-27-n72` | 0,724 | satisfacible | `floor500-tmax` | `floor10000-tmax` | no | **96,3 %** | sí |
| `battery-n800` | 0,730 | satisfacible | `floor10000-mid` | `floor10000-tmax` | no | 0,0 % | no |
| `battery-n200` | 0,752 | satisfacible | `floor10000-mid` | `floor10000-tmax` | no | 3,1 % | no |
| `battery-n400` | 0,779 | satisfacible | `floor10000-mid` | `floor10000-tmax` | no | 3,7 % | no |
| `battery-n50` | 0,823 | satisfacible | `floor10000-tmax` | `floor10000-tmax` | **sí** | **89,5 %** | sí |
| `area-26-n157` | 0,962 | satisfacible | `floor10000-tmax` | `floor10000-tmax` | **sí** | 25,0 % | no |
| `battery-n100` | 0,986 | satisfacible | `floor10000-mid` | `floor10000-tmax` | no | 0,0 % | no |
| `area-29-n43` | 1,210 | relleno forzado | `floor10000-mid` | `floor10000-mid` | **sí** | 0,6 % | sí |

En `battery-n50` los cuatro brazos `*-tmax` empatan exactamente (relleno 673 s, σ = 0 en los
cuatro): el ganador nominal entre ellos lo fija el desempate determinista del script y no significa
nada. En `area-27` el empate es solo entre tres de ellos (178–199 s, σ ≤ 9,9 s); el cuarto,
`floor10000-tmax`, promedia 1 727 s con σ = 2 190 s: dos semillas cierran la instancia con una ruta
(178 s) y la tercera se queda en dos (4 824 s). Su media no es un nivel, es el promedio de dos
desenlaces discretos, y por eso la σ de esa celda se traga toda comparación que la involucre. La
distinción que importa es `mid` contra `tmax`, y ahí el empate no existe.

### H1 — el predicado de relleno: **falsado**

**3 de 12 aciertos.** El falsador registrado en la §7 pedía una sola excepción, y hay **nueve**:

- **H1a (`rho_pad > 1` ⟹ ninguna celda baja el relleno ≥ 30 %) — se sostiene**, pero sobre una
  única instancia: `area-29-n43`, donde la mejor celda baja el relleno **0,6 %**. El mecanismo
  funciona donde aplica: con `k_hat` = 1 y 5 949 s de trabajo contra un piso de 7 200 s, ninguna
  configuración del techo toca el término que paga, y ninguna lo hace. Es la predicción más nítida
  del ciclo, y descansa en n = 1.
- **H1b (`rho_pad ≤ 1` ⟹ alguna celda baja el relleno ≥ 30 %) — falsada 9 veces de 11.** Solo
  `area-27` (96,3 %) y `battery-n50` (89,5 %) alcanzan el umbral. Las otras nueve instancias con el
  piso satisfacible se quedan entre **0,0 %** y **25,0 %**, incluida `area-26-n157` (25,0 %), que
  el ciclo anterior ya había marcado como fallo de relleno.

La correlación de Spearman entre `rho_pad` y la mejor caída de relleno sobre las 12 instancias es
**−0,039**: no hay relación monótona, ni débil, y el poco signo que hay apunta al revés de lo que
predice H1. Con `saturation_hat` es **+0,039** — el mismo número con el signo cambiado, porque
`rho_pad = (T_min/T_max) / saturation_hat` invierte exactamente el orden de rangos. El predicado no
ordena las instancias por lo que puede ganarse en ellas.

### H2 — el guard de régimen: **falsado, y por debajo de la regla trivial**

**3 de 12 aciertos**, contra **8 de 12** de la clase mayoritaria ("gana siempre `floor10000-mid`").
El falsador de la §7 pedía ≤ 9/12 **o** no superar a la clase mayoritaria; el guard falla las dos
condiciones a la vez. Es peor que no predecir nada.

La razón es estructural y se ve en la tabla de features: `rho_pad > 1` clasifica **una** instancia,
así que el guard es "usa `*-tmax` en todas menos en `area-29`", y `*-tmax` **no** es el ganador en
8 de esas 11. Un predicado con una clase de tamaño 1 no puede reproducir una partición 8/4.

### Las dos lecturas, lado a lado

Agregados sobre las 12 instancias (suma de relleno, suma de auto-cruces sobre calles, suma de
travel; media de balance; número de instancias con ruta degenerada o que fallan alguna puerta):

| política | Σ relleno (s) | Σ `crossings_road` | Σ travel (s) | balance medio | instancias degeneradas | fallos de puerta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **(a) mejor default único = `floor10000-mid`** (control) | 86 457 | **190,0** | 191 283 | **0,907** | **0** | **0** |
| `floor2000-mid` | 86 325 | 198,0 | 191 151 | 0,908 | 0 | 0 |
| `floor500-mid` | 86 195 | 202,0 | 191 021 | 0,911 | 0 | 0 |
| `floor100-mid` | 101 327 | 242,0 | 205 695 | 0,886 | 1 | 2 |
| `floor10000-tmax` | 77 417 | 286,3 | 183 694 | 0,864 | 1 | 1 |
| `floor2000-tmax` | **75 918** | 287,7 | 182 325 | 0,862 | 1 | 1 |
| `floor500-tmax` | 75 910 | 280,3 | **182 317** | 0,862 | 1 | 1 |
| `floor100-tmax` | 76 046 | 293,3 | 182 454 | 0,859 | 1 | 1 |
| **(b) guard de régimen** (`rho_pad > 1` → control, si no → `floor10000-tmax`) | 77 424 | 281,0 | 183 702 | 0,864 | 1 | 1 |

**(b) es indistinguible de aplicar `floor10000-tmax` a todo** — difiere en 7 s de relleno y 5,3
auto-cruces sobre 12 instancias — porque solo redirige una instancia. Compra −10 % de relleno y
−4 % de travel contra el control, y lo paga con **+48 % de auto-cruces sobre calles**, balance
0,907 → 0,864 y una instancia con ruta degenerada. Bajo el criterio de la §4 eso no es una ganadora
parcial: **falla**, porque el relleno solo se lee entre celdas que pasan las puertas, y `*-tmax`
no las pasa en `reference-n1607`.

El mejor default único sigue siendo el control, que gana 8 de 12 instancias y es el único (junto a
`floor2000-mid` y `floor500-mid`, indistinguibles de él) que pasa las puertas en las 12.

### Cuadro de predicciones

| # | predicción | resultado | veredicto |
| --- | --- | --- | --- |
| H1a | `rho_pad > 1` ⟹ ninguna celda baja el relleno ≥ 30 % | se cumple en la única instancia del régimen (0,6 %) | **no falsada, n = 1** |
| H1b | `rho_pad ≤ 1` ⟹ alguna celda baja el relleno ≥ 30 % | 2 de 11; ρ Spearman −0,039 | **falsada** |
| H2 | el régimen predice el ganador en ≥ 10/12 y supera a la clase mayoritaria | 3/12 contra 8/12 | **falsada** |
| ciclo | (b) mejora a (a) en algún agregado | (b) baja relleno y travel pero rompe cruces, balance y puertas | **falsada bajo el criterio** |

---

## Veredicto

**El predicado NO predice al ganador. `rho_pad` acierta 3 de 12 instancias contra 8 de 12 de la
regla trivial "gana siempre el control", y su correlación de Spearman con lo que hay para ganar en
cada instancia es −0,039.** El guard de régimen construido sobre él es, en el agregado,
indistinguible de aplicar `floor10000-tmax` a todas las instancias, y falla el criterio de
aceptación por auto-cruces sobre calles, balance y rutas degeneradas. **Ningún default de
producción cambia.**

Resultado negativo, publicado tal como estaba pre-registrado. Costó cero CPU de solver.

### Lo que sí queda establecido

1. **El mecanismo del piso infactible es real pero casi nunca se activa.** Donde `rho_pad > 1`
   (`area-29-n43`) el relleno es irreducible como predice el marco de precios marginales: 0,6 % de
   mejora entre ocho configuraciones. Pero **1 de 12 instancias** está en ese régimen. La serie
   había generalizado un mecanismo diagnosticado en instancias pequeñas y ralas a una explicación
   de por qué no hay configuración ganadora; **esa generalización no se sostiene**. El relleno de
   las otras once instancias tiene otra causa.
2. **`area-26-n157` no está en régimen de relleno forzado.** Su `rho_pad` es 0,962: el piso es
   satisfacible a `k_hat` = 3. La lectura previa — "su relleno es geometría irreducible" — no puede
   apoyarse en la infactibilidad del piso, porque el piso ahí es factible. Que su mejor caída
   medida sea 25 % (bajo el umbral de 30 %) sigue siendo cierto; lo que cae es la explicación.
3. **La partición de ganadores es 8 control / 4 `*-tmax`, y no la explican ni densidad, ni
   diámetro, ni elongación, ni `n`, ni saturación a priori.** `reference-n1607` (22 árboles/km²) y
   `battery-n1000` (276/km²) tienen el mismo ganador; `battery-n50` (65/km²) y `area-27` (172/km²)
   comparten el otro. Las features geométricas puras están publicadas en el CSV para que cualquier
   ciclo posterior las use sin recomputarlas.

### Observación post-hoc — declarada como tal, NO probada

Al diagnosticar **por qué** falló el predicado aparece un patrón que este ciclo **no** registró y
**no** prueba, y que por lo tanto no tiene ningún estatus de resultado:

las dos instancias con caídas grandes de relleno (`area-27` 96,3 %, `battery-n50` 89,5 %) son
exactamente aquellas donde el brazo `*-tmax` **elimina una ruta**: `k` pasa de 2,0 a 1,0–1,33. En
`battery-sparse-n250`, que ahorra 1 ruta de 6, la caída es 10,6 %; donde `k` no se mueve
(`area-26`, `area-29`, `battery-n100`, `battery-n800`, `n=1607`) la caída es ≤ 25 %. Lo que el
techo a `T_max` compra no es "menos relleno" sino **una ruta menos**, y el relleno cae en
proporción a la fracción de flota ahorrada.

Tres razones para no venderlo como hallazgo:

- **`k` de la solución de control es post-solver.** Su versión pre-solver evidente —
  `work_lb / (k_hat · 9 000) > 1`, o sea "el techo blando obliga a abrir una ruta extra" — se
  cumple en 8 de las 12 instancias, incluidas `reference-n1607` (1,186) y `battery-n800` (1,096),
  donde `*-tmax` **no** ahorra ninguna ruta. Como predicado pre-solver **también fallaría**.
- Es un patrón **elegido después de ver qué instancias ganaron**, exactamente lo que la §1 se
  comprometió a declarar si ocurría.
- Serían **tres** predicados probados sobre las mismas 12 instancias, sin holdout posible.

Queda anotado como hipótesis para un ciclo futuro con su propio pre-registro, no como conclusión.

### Lo que queda descartado

- **`rho_pad` como guard de régimen**: falsado. No se reabre sin una suite de instancias donde el
  régimen de relleno forzado no sea 1 de 12.
- **"El relleno es irreducible porque el piso es infactible" como explicación general**: falsado
  fuera de `area-29`. Cualquier ciclo que quiera atribuir relleno a esa causa tiene que mostrar
  `rho_pad > 1` en su instancia.
- **La idea de que existe un régimen legible desde la geometría pura** (densidad, diámetro,
  elongación, `n`): sin apoyo en estos datos. No está refutada — este ciclo probó dos predicados,
  no todos los posibles — pero ninguna de las features publicadas separa a los dos grupos de
  ganadores.

### Salida hacia la tesis

Esto es material de **discusión y trabajo futuro**, no un cambio de producto. La formulación
honesta de lo que la serie sabe hoy queda: *trece ciclos no encontraron una configuración ganadora
global; la hipótesis de que el ganador es regional y el régimen predecible desde la instancia se
probó con dos predicados mecanicistas y ninguno predice mejor que elegir siempre la configuración
por defecto.* Con n = 12 instancias no hay holdout, así que ni siquiera un predicado acertado
habría sido un modelo validado: habría sido una regla mecanicista verificada. Este no acertó.
