# Ancla alcanzable: acotar el relleno por arriba con un camino TSP partido

**Fecha:** 2026-07-22
**Estado al commitear esta sección:** pre-registro. Diseño, construcción, instancias, métricas,
predicciones y reglas de decisión se commitean **antes** de medir nada. Los resultados se agregan
después, sin tocar el criterio.

Todo es **medición pura**: no se resuelve ningún VRP nuevo, no se juzga ningún brazo nuevo y no se
toca la configuración de producción del solver. Los defaults (`spatial_term`, `PenaltyConfig`
actual, coeficiente de span espacial 3) quedan intactos. Lo nuevo es un comando opt-in.

---

## Por qué este ciclo

La métrica que juzga el relleno en toda la serie desde `sweep-metrology-20260720.md` es

```text
relleno_msf := travel_total − MSF_k
```

donde `MSF_k` es el bosque generador mínimo de `k` componentes sobre la matriz simetrizada
`min(d_ij, d_ji)` (= MST menos sus `k − 1` aristas más pesadas). Es una **cota inferior válida**:
`k` caminos abiertos que cubren `n` nodos *son* un bosque generador de `k` componentes.

Pero es una **relajación**. Ignora la restricción de grado 2 de un camino, así que ningún recorrido
real puede alcanzarla. El propio reporte de metrología lo admite y estima la brecha en **10–30 %**
a partir de literatura euclídea general, **no de una medición sobre estas instancias**. De ahí sale
el umbral de relleno de la serie (**−30 %**), fijado como **juicio** con análisis de sensibilidad, y
de ahí sale el riesgo que ese reporte dejó escrito: *«se parece a mover la portería»*.

El resultado es que **el criterio más disputado de la serie —el que bloqueó tres ciclos en
`area-26-n157` y luego los desbloqueó— se apoya en una cota que nadie ha medido.** Este ciclo la
mide.

---

## La construcción

Simétrica a la que ya existe, y con la misma operación elemental:

```text
MSF_k = MST          menos las k−1 aristas más pesadas  → cota INFERIOR (relajación)
UB_k  = camino TSP   menos las k−1 aristas más pesadas  → cota SUPERIOR (construida)
```

Partir un camino TSP abierto por sus `k − 1` aristas más caras deja `k` caminos abiertos que
cubren todos los nodos: **una solución factible real**, no una relajación. Por eso `UB_k` no es una
cota en el sentido en que lo es `MSF_k` — es un **recorrido efectivamente construido**, y el
relleno medido contra él es «distancia a algo que sabemos hacer» en vez de «distancia a algo que
nadie puede alcanzar».

En `bounds.py` ambas cotas comparten la primitiva `without_heaviest_edges(edges, k)`: la diferencia
entre una y otra es **sólo** la estructura conexa a la que se le aplica el corte.

### Dos costos, y por qué se reportan los dos

- **`ub_k_sec`** — suma de los tramos sobre la matriz **simetrizada**. Es el objeto directamente
  comparable con `MSF_k`: ambas cifras acotan el **mismo** óptimo simetrizado, una por abajo y otra
  por arriba. La brecha entre ellas es la respuesta a la pregunta (a).
- **`ub_k_directed_sec`** — suma de los tramos sobre la matriz **real dirigida**, cada tramo
  recorrido en su dirección más barata (un censista puede caminar la ruta en cualquier sentido).
  Es el costo que un equipo pagaría de verdad.

La caminata a pie es casi simétrica, así que se espera que difieran poco; se publican ambos para
que la afirmación «es alcanzable» no dependa de la simetrización.

### Verificación de factibilidad, declarada por adelantado

Un conjunto de `k` caminos que cubre todos los nodos no es útil como ancla si viola el techo
operativo. Para cada `(instancia, k)` se computa la duración de cada tramo como
`travel dirigido + 120 s × paradas` y se compara contra `T_max = 10 800 s`.

**Compromiso:** si algún tramo excede `T_max`, se reporta explícitamente en las columnas
`ub_routes_over_tmax` y `ub_tmax_feasible`, y esa fila se declara **no alcanzable bajo la
configuración censal** en el texto del reporte. No se esconde ni se omite la fila.

---

## Preguntas a responder

**(a) ¿Cuán floja es `MSF_k`?** Para cada instancia y cada `k`, la brecha
`gap = UB_k − MSF_k` en segundos y en porcentaje de `MSF_k`. Esa brecha **es** la incertidumbre
real del criterio de relleno de toda la serie.

**(b) ¿Cambia el veredicto de relleno de algún brazo ya juzgado?** El ciclo de metrología encontró
que 14 de 28 celdas cambiaban de veredicto al corregir el cero. Esta es la misma pregunta un nivel
más fino: re-juzgar con `relleno_ub` las mismas celdas ya juzgadas con `relleno_msf`.

**(c) ¿El umbral de −30 % sigue siendo defendible, o quedó holgado/estrecho?**

---

## Aritmética previa: hacia dónde debería moverse el veredicto

Esto se fija **antes** de medir, para que el resultado pueda confirmarlo o refutarlo en vez de
racionalizarlo después.

Con el mismo `k` en ambos brazos, la variación relativa que juzga el criterio es

```text
Δ%  =  (travel_arm − travel_actual) / (travel_actual − ancla)
```

El numerador **no depende del ancla**. El denominador sí, y como `UB_k > MSF_k`, el denominador
bajo el ancla alcanzable es **más chico**. Por lo tanto:

> **Predicción pre-registrada 1.** Para todo brazo que mejore el relleno respecto de `actual`,
> `|Δ%|` medido contra `UB_k` será **mayor o igual** que medido contra `MSF_k`. Es decir: el ancla
> alcanzable es **más indulgente**, y el criterio anclado en `MSF_k` es el **conservador** de los
> dos.
>
> **Predicción pre-registrada 2.** En consecuencia, ninguna celda que **pasaba** bajo `MSF_k` puede
> **fallar** bajo `UB_k` (con `k` igual). Los únicos cambios de veredicto posibles son
> fallo → aprobación. Si se observa un cambio aprobación → fallo, la causa sólo puede ser un `k`
> distinto entre brazos, y se investigará y reportará como tal.
>
> **Predicción pre-registrada 3.** La brecha `gap_pct` será **mayor en las instancias chicas y
> dispersas** que en las densas: cuanto más disperso el conjunto, más aristas largas obligadas y
> más se aleja el MST de un camino factible.

Si la medición contradice cualquiera de las tres, se reporta la contradicción con la misma fuerza
que una confirmación.

### La trampa del denominador negativo

`relleno_ub` **puede ser negativo**: el VRP optimiza conjuntamente y puede batir a un camino TSP
partido a posteriori. Eso no es un error de contabilidad —a diferencia de `travel < MSF_k`, que sí
lo sería— sino un resultado real: significa que el brazo encontró algo mejor que el ancla
construida.

**Compromiso, escrito antes de medir:** `relleno_ub` **no se recorta en cero** y el driver **no
aborta** al verlo negativo (a diferencia de `relleno_msf`, donde el corte y el aborto sí
corresponden porque `MSF_k` es una cota demostrada). Y si `relleno_ub(actual) ≤ 0` en alguna
instancia, la variación porcentual queda **indefinida** ahí: se reportará como **indefinida**, con
esas palabras, y no se sustituirá por otra cifra ni se omitirá la instancia.

---

## Reglas de decisión

Fijadas aquí, antes de ver ningún número.

**Regla A — cuán floja es la cota.** Se clasifica la brecha `gap_pct = (UB_k − MSF_k)/MSF_k` en la
`k` de operación de cada instancia:

| `gap_pct` | Lectura |
| --- | --- |
| ≤ 10 % | La relajación es **irrelevante**: `MSF_k` sirve como ancla y el debate se cierra. |
| 10 – 30 % | **Material**: coincide con la estimación 10–30 % que la serie asumió sin medir. |
| > 30 % | **Dominante**: la serie subestimó la incertidumbre de su propio criterio. |

**Regla B — estabilidad del veredicto.** Se re-juzgan con `relleno_ub`, y con el **mismo umbral de
−30 %**, las celdas de la serie que ya tienen veredicto de áreas. Si **ninguna** cambia de lado, el
umbral es estable frente al cambio de ancla. Se publica el conteo exacto de cambios y su dirección,
sea cual sea.

**Regla C — defensibilidad del umbral.** Para cada brazo se computa el umbral anclado en `MSF_k`
que produciría el **mismo** veredicto que −30 % anclado en `UB_k`, y se publica la banda resultante.
Lectura pre-registrada:

- Si la banda **contiene** −30 %, el número elegido estaba bien centrado y se dice así.
- Si la banda queda **por completo** más laxa que −30 %, el umbral era **estrecho** (exigía de más).
- Si queda **por completo** más exigente, el umbral era **holgado** (regalaba), y se dice así
  aunque eso debilite los veredictos positivos de la serie, incluido el de `feasible-floor-b095`.

**No se renegocia el umbral en este ciclo.** Este ciclo mide la incertidumbre del umbral; no lo
cambia. Cualquier cambio de umbral sería material para otro ciclo, con su propio pre-registro.

---

## Diseño de la medición

`instance_tsp_anchor`, aritmética + un TSP de una ruta por instancia. **Sin brazos, sin semillas,
sin barrido de VRP.** El camino TSP depende sólo de la instancia, no de la configuración del
solver ni del brazo, así que una sola resolución por instancia sirve para todos los `k`.

| Grupo | Instancias | `k` | Límite de tiempo del TSP |
| --- | --- | --- | --- |
| Áreas reales (alcance mínimo) | `area-26-n157`, `area-27-n72`, `area-29-n43` | 1–6 | 120 s |
| Batería chica | `battery-n{50,100,200,400,800,1000}`, `battery-sparse-n{250,500}` | 1–6 | 120 s |
| Referencia | `reference-n1607` | 1–30 | 600 s |

`reference-n1607` es demasiado grande para llamar óptimo a un TSP con este presupuesto.
**Compromiso:** su fila se reporta como **cota superior construida con esfuerzo acotado**, nunca
como óptimo, y se acompaña de la prueba de convergencia de abajo.

### Prueba de convergencia (para no llamar «casi óptimo» a lo que no lo es)

OR-Tools no expone un gap de optimalidad para esta formulación, así que la calidad del camino se
mide empíricamente: cada instancia se resuelve **también** con un límite de 30 s, y se publica
`UB_1` a ambos límites.

- Cambio relativo **< 0.5 %** entre 30 s y el límite largo → se declara **convergido** y el ancla
  se usa sin reservas.
- Cambio **≥ 0.5 %** → se declara **no convergido**, la cifra se reporta como cota superior floja
  (que sigue siendo válida como ancla superior, sólo que menos ajustada) y la brecha `gap_pct` de
  esa instancia se lee como **máximo**, no como valor.

En las áreas chicas (n = 43, 72, 157) se espera convergencia; en `reference-n1607`, no
necesariamente. Se reporta lo que salga.

### Nota de ejecución

Las instancias se corren en flujos paralelos sobre la misma máquina, así que el `wall_clock` no es
homogéneo y **no se usa para juzgar nada**. Importa poco en este ciclo: el objeto medido —el camino
TSP y las cotas derivadas— es **determinista dado el límite de tiempo**, salvo por el efecto de la
contención de CPU sobre cuántas iteraciones de GLS entran en ese límite. Ese efecto es
exactamente lo que la prueba de convergencia acota.

### Sobre no comparar contra medias publicadas

`stops-penalty-sweep-20260722.md` midió que la varianza **entre corridas** supera a la varianza
entre semillas dentro de una corrida (el travel de `feasible-floor-b095` se movió de 59 971 a
62 751 s entre ciclos, un salto mayor que su desviación entre semillas).

Consecuencia asumida aquí: **este ciclo no compara ninguna cifra de travel contra medias publicadas
en reportes anteriores.** Las cotas `MSF_k` y `UB_k` no dependen del solver de VRP ni de semillas
—son función de la instancia y de `k`—, así que sí son comparables entre ciclos; el travel de los
brazos **no**. Por eso el re-juicio de la Regla B se hace **fila a fila sobre los CSV ya
publicados**, que es aritmética sobre datos guardados, y no contra medias re-narradas. Cuando el
reporte cite un Δ% de un brazo, será el recomputado sobre esas filas y con su propia ancla, no una
cifra copiada de otro reporte.

---

## Qué NO responde este ciclo

- No dice si algún brazo gana. No hay brazos.
- No cambia el umbral de −30 %. Mide su incertidumbre.
- No mide la varianza entre corridas del solver: no corre el solver de VRP.
- No produce un `UB_k` óptimo, sólo uno construido. Un `UB_k` más ajustado sólo podría **estrechar**
  la brecha reportada, nunca ampliarla, así que las cifras de (a) son **cotas superiores de la
  incertidumbre** — que es el lado conservador para el argumento.

---

## Compromisos de reporte

1. Este pre-registro se **commitea antes de medir**, como los seis anteriores de la serie. El
   commit queda identificado por hash en la sección de resultados.
2. El criterio y las reglas de decisión **no se tocan** una vez leídos los resultados.
3. **Si el resultado es negativo se reporta igual de fuerte que uno positivo.** En este ciclo, el
   resultado incómodo sería que la brecha resultara **dominante**: eso debilitaría retroactivamente
   los veredictos de relleno de toda la serie, incluido el que desbloqueó `area-26-n157`. Se
   reportará con todas sus letras si ocurre.
4. Las tres predicciones pre-registradas se confrontan una por una, con su resultado.

---

## Reproducción

```bash
# Cargar la suite congelada (UUID deterministas, la cache de OSRM acierta)
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py load_instances

# Ancla construida: áreas reales + batería chica
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py instance_tsp_anchor \
    --csv docs/experiments/tsp-achievable-anchor-20260722-anchor.csv \
    --k-max 6 --tsp-time-limit 120 \
    --instance area-26-n157 area-27-n72 area-29-n43 \
               battery-n50 battery-n100 battery-n200 battery-n400 \
               battery-n800 battery-n1000 battery-sparse-n250 battery-sparse-n500

# Referencia, con esfuerzo acotado y k hasta el de operación
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py instance_tsp_anchor \
    --csv docs/experiments/tsp-achievable-anchor-20260722-anchor-n1607.csv \
    --k-max 30 --tsp-time-limit 600 --instance reference-n1607

# Prueba de convergencia (mismo comando, límite corto)
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py instance_tsp_anchor \
    --csv docs/experiments/tsp-achievable-anchor-20260722-converge30.csv \
    --k-max 1 --tsp-time-limit 30 \
    --instance area-26-n157 area-27-n72 area-29-n43 \
               battery-n50 battery-n100 battery-n200 battery-n400 \
               battery-n800 battery-n1000 battery-sparse-n250 battery-sparse-n500 \
               reference-n1607

# Re-juicio de las celdas ya juzgadas contra el ancla alcanzable
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py rejudge_relleno \
    --decomposition docs/experiments/sweep-metrology-20260720-decomposition.csv \
    --anchor docs/experiments/tsp-achievable-anchor-20260722-anchor-all.csv \
    --out docs/experiments/tsp-achievable-anchor-20260722-rejudge.csv \
    --sweep docs/experiments/sweep-metrology-20260720-h2h-actual.csv \
            docs/experiments/sweep-metrology-20260720-h2h-feasible-floor-b095.csv \
            docs/experiments/sweep-metrology-20260720-h2h-no-floor-stops10.csv \
            docs/experiments/sweep-metrology-20260720-h2h-feasible-floor-b060-stops10.csv \
            docs/experiments/stops-penalty-sweep-20260722-actual.csv \
            docs/experiments/stops-penalty-sweep-20260722-feasible-floor-b095.csv
```

---

---

## Resultados

**El pre-registro de arriba quedó en el commit `403bc0b`** («docs(experiments): pre-register the
achievable-anchor measurement»), y el código que lo implementa en `3a4c166`. Todo lo que sigue se
escribió después de medir; nada de lo de arriba se tocó.

Datos: `tsp-achievable-anchor-20260722-anchor.csv` (11 instancias × k=1..6),
`-anchor-n1607.csv` (k=1..30), `-anchor-all.csv` (unión), `-converge30.csv` (prueba de
convergencia) y `-rejudge.csv` (**360 filas** re-juzgadas de los dos ciclos más recientes).

Precisión sobre `-anchor-all.csv`, que el bloque de Reproducción consume sin decir de dónde sale:
**ningún comando lo produce.** Los dos grupos corren con límites de TSP distintos (120 s y 600 s),
así que no salen de una sola invocación; el archivo es la concatenación literal de los dos:

```bash
cp docs/experiments/tsp-achievable-anchor-20260722-anchor.csv \
   docs/experiments/tsp-achievable-anchor-20260722-anchor-all.csv
tail -n +2 docs/experiments/tsp-achievable-anchor-20260722-anchor-n1607.csv \
   >> docs/experiments/tsp-achievable-anchor-20260722-anchor-all.csv
```

### Validación de la instrumentación

Las cuatro cifras de `MSF_k` que la serie ya había publicado se reproducen **exactamente**:
`area-26-n157` k=3 → 3 618 s, `area-27-n72` k=2 → 914 s, `area-29-n43` k=1 → 789 s,
`reference-n1607` k=25 → 30 823 s. El ancla nueva se construye sobre el mismo código de cota que
la serie viene usando.

Segundo hecho, no previsto pero cómodo: **`ub_k_sec` y `ub_k_directed_sec` coinciden hasta el
segundo en las 96 filas.** La matriz de caminata de OSRM es simétrica en estas instancias, así que
la afirmación «es alcanzable» no depende en absoluto de la simetrización. La columna dirigida se
mantiene porque esa simetría es un hecho medido de este conjunto de datos, no una garantía.

### Prueba de convergencia

`UB_1` a 30 s contra el límite largo (120 s, y 600 s en la referencia):

| Instancia | n | `UB_1` @30 s | `UB_1` @largo | Cambio | Estado |
| --- | ---: | ---: | ---: | ---: | --- |
| `area-29-n43` | 43 | 955 | 955 | 0.00 % | convergido |
| `battery-n50` | 50 | 3 266 | 3 266 | 0.00 % | convergido |
| `area-27-n72` | 72 | 1 425 | 1 425 | 0.00 % | convergido |
| `battery-n100` | 100 | 4 065 | 4 065 | 0.00 % | convergido |
| `area-26-n157` | 157 | 5 131 | 5 131 | 0.00 % | convergido |
| `battery-n200` | 200 | 7 653 | 7 620 | 0.43 % | convergido |
| `battery-sparse-n250` | 250 | 15 298 | 15 298 | 0.00 % | convergido |
| `battery-n400` | 400 | 12 634 | 12 634 | 0.00 % | convergido |
| `battery-sparse-n500` | 500 | 19 787 | 19 785 | 0.01 % | convergido |
| `battery-n800` | 800 | 19 913 | 19 716 | 1.00 % | **NO convergido** |
| `battery-n1000` | 1 000 | 24 830 | 24 716 | 0.46 % | convergido |
| `reference-n1607` | 1 607 | 58 150 | 55 644 | **4.50 %** | **NO convergido** |

**Las tres áreas reales —el alcance mínimo del ciclo— convergen exactamente**: cuadruplicar el
presupuesto no mueve ni un segundo. Ahí el ancla se usa sin reservas.

`battery-n800` y `reference-n1607` **no** convergen. Conforme a la regla pre-registrada, sus
brechas se leen como **máximos, no como valores**: un TSP mejor sólo puede bajar `UB_k` y estrechar
la brecha. Ninguna cifra de la referencia se presenta como óptima en este reporte.

### (a) Cuán floja es `MSF_k` — la respuesta principal

Brecha `UB_k − MSF_k` en la `k` de operación de cada instancia:

| Instancia | n | k | `MSF_k` | `UB_k` | Brecha | **Brecha %** | Lectura (Regla A) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `area-27-n72` | 72 | 2 | 914 | 1 036 | 122 | **13.3 %** | material |
| `area-26-n157` | 157 | 3 | 3 618 | 4 290 | 672 | **18.6 %** | material |
| `area-29-n43` | 43 | 1 | 789 | 955 | 166 | **21.1 %** | material |
| `reference-n1607` | 1 607 | 25 | 30 823 | 39 695 | 8 872 | **≤28.8 %** | material (máximo) |

**Las cuatro caen dentro de la banda 10–30 % que el reporte de metrología asumió sin medirla.**
Ninguna es «irrelevante» (≤10 %) y ninguna es «dominante» (>30 %). La estimación que la serie tomó
prestada de la literatura euclídea resultó **correcta para estas instancias**, y ahora está medida
en vez de supuesta.

En términos concretos: de los 1 524 s que `actual` mostraba como relleno en `area-26-n157`, **672 s
—el 44 %— son la propia flojedad de la cota**, no relleno ni geometría del brazo. En
`reference-n1607`, de 29 508 s de relleno medido, hasta 8 872 s son flojedad de la cota.

Brecha % completa, por instancia y `k`:

| Instancia | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `area-29-n43` | 21.1 | 24.3 | 23.6 | 23.4 | 23.4 | 24.9 |
| `battery-n50` | 19.0 | 22.2 | 22.8 | 24.7 | 27.5 | 28.8 |
| `area-27-n72` | 9.4 | 13.3 | 15.5 | 7.8 | 8.2 | 8.6 |
| `battery-n100` | 20.6 | 24.5 | 25.5 | 27.5 | 29.4 | 31.2 |
| `area-26-n157` | 20.6 | 19.4 | 18.6 | 19.7 | 20.5 | 20.8 |
| `battery-n200` | 29.2 | 32.9 | 35.7 | 36.6 | 36.3 | 36.6 |
| `battery-sparse-n250` | 23.0 | 24.0 | 24.8 | 24.8 | 24.9 | 25.0 |
| `battery-n400` | 32.6 | 34.7 | 36.2 | 36.6 | 38.4 | 37.8 |
| `battery-sparse-n500` | 30.0 | 31.1 | 31.9 | 32.0 | 32.0 | 32.1 |
| `battery-n800` | 31.5 | 31.4 | 31.7 | 31.8 | 32.6 | 32.3 |
| `battery-n1000` | 37.4 | 37.7 | 38.1 | 38.6 | 37.7 | 37.7 |
| `reference-n1607` | 29.9 | 35.5 | 35.2 | 34.7 | 33.8 | 33.5 |

### Límite del ancla: dónde no respeta `T_max`

Compromiso pre-registrado, cumplido sin adornos. En la `k` de operación:

| Instancia | k | Tramo más largo | ¿≤ `T_max` (10 800 s)? | Tramos que exceden |
| --- | ---: | ---: | :---: | ---: |
| `area-27-n72` | 2 | 5 357 s | ✅ | 0 |
| `area-29-n43` | 1 | 6 115 s | ✅ | 0 |
| `area-26-n157` | 3 | 13 943 s | ❌ | 1 de 3 |
| `reference-n1607` | 25 | 40 408 s | ❌ | 8 de 25 |

Cortar por las aristas más caras reparte los **nodos** donde el mapa lo pide, no el **tiempo** de
forma pareja, así que los tramos quedan desbalanceados. En `area-26-n157` el ancla se vuelve
factible bajo `T_max` recién en **k=5** (tramo máximo 8 516 s).

**Qué significa exactamente, y qué no.** `UB_k` acota el óptimo de *k caminos que cubren todos los
nodos* **sin** la restricción de duración. Donde `T_max` no binda (`area-27`, `area-29`) es
directamente una solución desplegable. Donde sí binda (`area-26` a k=3, la referencia a k=25) el
óptimo **con** `T_max` está en algún punto **por encima** de `UB_k`.

Eso empuja en la dirección conservadora del argumento de este ciclo: el relleno realmente evitable
es **aún menor** que `relleno_ub`, y `MSF_k` es **aún más flojo** de lo que dicen las cifras de la
tabla (a). Ninguna conclusión de abajo depende de suponer lo contrario.

### (b) ¿Cambia algún veredicto ya emitido?

Re-juicio de las 12 celdas de área de los dos ciclos más recientes, con el **mismo umbral de
−30 %** sobre cada ancla. Cada Δ% se computa **dentro de su propio ciclo**, contra el `actual`
re-corrido en ese ciclo — nunca contra medias publicadas en otro reporte, conforme al hallazgo de
`stops-penalty-sweep-20260722.md`.

| Ciclo | Brazo | Instancia | Δ% vs `MSF_k` | Δ% vs `UB_k` | Veredicto MSF | Veredicto UB |
| --- | --- | --- | ---: | ---: | :---: | :---: |
| metrología | `feasible-floor-b095` | `area-26-n157` | −50.1 | **−89.6** | ✅ | ✅ |
| metrología | `feasible-floor-b095` | `area-27-n72` | −96.0 | −98.5 | ✅ | ✅ |
| metrología | `feasible-floor-b095` | `area-29-n43` | −83.0 | −95.9 | ✅ | ✅ |
| metrología | `no-floor-stops10` | `area-26-n157` | −49.1 | **−87.8** | ✅ | ✅ |
| metrología | `no-floor-stops10` | `area-27-n72` | −95.9 | −98.4 | ✅ | ✅ |
| metrología | `no-floor-stops10` | `area-29-n43` | −83.0 | −95.9 | ✅ | ✅ |
| metrología | `feasible-floor-b060-stops10` | `area-26-n157` | −51.9 | **−92.8** | ✅ | ✅ |
| metrología | `feasible-floor-b060-stops10` | `area-27-n72` | −95.9 | −98.4 | ✅ | ✅ |
| metrología | `feasible-floor-b060-stops10` | `area-29-n43` | −83.0 | −95.9 | ✅ | ✅ |
| piso de paradas | `feasible-floor-b095` | `area-26-n157` | −51.8 | **−90.2** | ✅ | ✅ |
| piso de paradas | `feasible-floor-b095` | `area-27-n72` | −96.0 | −98.5 | ✅ | ✅ |
| piso de paradas | `feasible-floor-b095` | `area-29-n43` | −83.1 | −95.9 | ✅ | ✅ |

**Cero cambios de veredicto en 12 de 12 celdas.** Todas pasaban y todas siguen pasando; lo único
que cambia es el **margen**, y siempre a favor del brazo.

Contraste con el ciclo de metrología, que es lo que esta pregunta pedía comparar: allí **14 de 28
celdas cambiaban de lado** al corregir el cero. Aquí, **0 de 12**. El primer arreglo del
instrumento (de `nn̄` a `MSF_k`) fue un cambio **cualitativo** que reescribió veredictos; este
segundo (de `MSF_k` a `UB_k`) es **cuantitativo**: mueve los márgenes, no las conclusiones.

#### La `k` no coincide en `area-27-n72`, y el pre-registro obliga a decirlo

La aritmética previa de arriba está escrita **«con el mismo `k` en ambos brazos»**, y el
pre-registro se comprometió a investigar y reportar cualquier `k` distinta entre brazos. En dos de
las tres áreas la condición se cumple (`area-26-n157`: actual y brazos a k=3; `area-29-n43`: todos
a k=1). En **`area-27-n72` no**: `actual` corre a **k=2** y los tres brazos a **k=1**, así que cada
lado se juzga contra su propia ancla (`MSF_2`=914 / `UB_2`=1 036 para `actual`; `MSF_1`=1 303 /
`UB_1`=1 425 para los brazos).

Por eso el Δ% de la tabla es la variación relativa del **relleno**, con cada lado contra el ancla
de su propia `k`:

```text
Δ%  =  (relleno_arm − relleno_actual) / relleno_actual,    relleno_X = travel_X − ancla(k_X)
```

que es algebraicamente idéntica a la forma `(travel_arm − travel_actual) / (travel_actual − ancla)`
del pre-registro **cuando `k` coincide** —de ahí que las cifras de `area-26` y `area-29` salgan
iguales por cualquiera de las dos— y sólo difiere en `area-27`, donde la del pre-registro no está
definida por tener dos anclas.

Consecuencias, sin maquillar:

- La **demostración** de la Predicción 1 (denominador más chico porque `UB_k > MSF_k` a `k` fija)
  **no aplica** a las tres celdas de `area-27`. Ahí la predicción se cumple igual —96.0 → −98.5—
  pero como hecho medido, no como corolario aritmético.
- El extremo **−29.2 %** de la banda de la Regla C sale precisamente de una celda con `k` distinta
  entre brazos. Es el extremo más cercano a −30 %, así que si se descarta, la banda se **aleja**
  más de −30 % en vez de acercarse: la conclusión (c) no depende de esa celda.
- No hay ningún cambio de veredicto que atribuir a la `k`: las tres celdas de `area-27` pasan
  holgadamente contra ambas anclas.

**El hallazgo más fuerte de la sección está en `area-26-n157`.** Su relleno, la instancia que
bloqueó tres ciclos de la serie, pasa de −50 % a **−90 %** contra el ancla alcanzable. Y en **6 de
las 360 filas** el relleno contra el ancla es **negativo**:

| Instancia | Brazo | Semilla | k | travel | `UB_3` | `relleno_ub` |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `area-26-n157` | `no-floor-stops10` | 2 | 3 | 4 246 | 4 290 | **−44** |
| `area-26-n157` | `feasible-floor-b095` | 5 | 3 | 4 272 | 4 290 | **−18** |
| `area-26-n157` | `feasible-floor-b060-stops10` | 2 | 3 | 4 275 | 4 290 | **−15** |
| `area-26-n157` | `feasible-floor-b095` | 3 | 3 | 4 277 | 4 290 | **−13** |

La tabla tiene **4 filas y el conteo dice 6** porque dos de esas celdas —`feasible-floor-b095`
semillas 3 y 5— aparecen en los **dos** ciclos re-juzgados: en `area-26-n157` el solver reprodujo
esas corridas segundo a segundo entre el ciclo de metrología y el de piso de paradas (4 277 y
4 272 s en ambos), así que cada una cuenta dos veces en las 360 filas. Celdas distintas que baten
al ancla: **4**. Es también un dato sobre la varianza entre corridas: en esta instancia chica es
nula, a diferencia de lo medido en `reference-n1607`.

Conforme al compromiso pre-registrado, **no se recortan en cero y el driver no aborta**: `UB_k` es
un recorrido construido, no una cota, y batirlo es un resultado legítimo. Y es el resultado más
informativo del ciclo:

> **En `area-26-n157` los brazos de la serie ya alcanzan —y a veces superan— el mejor recorrido que
> sabemos construir. Lo que la serie pasó tres ciclos intentando eliminar ahí no era relleno: era
> el costo de recorrer esa área.**

El ciclo de metrología lo había argumentado con una cota inalcanzable; aquí queda medido contra un
recorrido concreto que el solver iguala.

### (c) ¿Sigue siendo defendible el umbral de −30 %?

Regla C: para cada celda, el umbral anclado en `MSF_k` que produciría el **mismo** veredicto que
−30 % anclado en `UB_k`.

| Instancia | Umbral `MSF_k` equivalente a −30 % sobre `UB_k` |
| --- | ---: |
| `area-26-n157` (metrología) | −16.8 % |
| `area-26-n157` (piso de paradas) | −17.2 % |
| `area-29-n43` | −26.0 % |
| `area-27-n72` | −29.2 % |

**Banda equivalente: [−29.2 %, −16.8 %]. No contiene −30 %.**

Aplicando la regla pre-registrada al pie de la letra: la banda queda **por completo del lado menos
exigente**, así que **el umbral de −30 % anclado en `MSF_k` era estrecho — exigía de más**. Para
obtener el mismo veredicto que un −30 % sobre el ancla alcanzable habría bastado con pedir entre
−17 % y −29 % sobre `MSF_k`.

Esto responde de frente al riesgo que el reporte de metrología dejó declarado:

> **El umbral no se movió hacia donde convenía. Se movió, sin que nadie lo supiera, hacia el lado
> conservador.** El −30 % sobre `MSF_k` es **más duro** que su equivalente sobre un ancla
> alcanzable, no más blando. Ningún veredicto positivo de la serie se regaló por haber elegido ese
> número: todos los brazos que pasaron habrían pasado también con el criterio anclado en un
> recorrido construido, y con márgenes mayores.

La acusación de «mover la portería» queda **refutada por medición** en la dirección que importa: la
portería quedó donde estaba o más lejos, nunca más cerca.

Corolario aritmético, ya visible en el pre-registro y ahora cuantificado: como `UB_k > MSF_k`, el
criterio anclado en `MSF_k` es **estructuralmente** el conservador de los dos. Cualquier ciclo
futuro que use `relleno_msf` está usando la regla estricta.

### Las tres predicciones pre-registradas, una por una

**Predicción 1 — `|Δ%|` mayor contra `UB_k` que contra `MSF_k`. CONFIRMADA**, en las 12 celdas sin
excepción (p. ej. −50.1 % → −89.6 %; −96.0 % → −98.5 %). En 9 de las 12 lo es por el corolario
aritmético pre-registrado; en las 3 de `area-27-n72` lo es como hecho medido, porque ahí la `k`
difiere entre `actual` y los brazos y la demostración no aplica (ver la nota de la sección (b)).

**Predicción 2 — ninguna celda pasa de aprobación a fallo. CONFIRMADA**: 0 cambios en 12 celdas, y
los únicos movimientos posibles (fallo → aprobación) tampoco se dieron porque las 12 ya pasaban.

**Predicción 3 — brecha mayor en instancias chicas y dispersas que en densas. REFUTADA**, y con
claridad. La brecha **crece con `n`** (k=3: `battery-n50` 22.8 % → `battery-n1000` 38.1 %), y las
dispersas quedan **por debajo** de las densas de tamaño comparable: `battery-sparse-n250` 24.8 %
contra `battery-n200` 35.7 %; `battery-sparse-n500` 31.9 % contra `battery-n400` 36.2 %.

Se reporta la refutación con la misma fuerza que las confirmaciones, y con su matiz: parte del
crecimiento con `n` es **calidad del TSP**, no geometría — a mayor `n` el camino está más lejos del
óptimo, lo que infla `UB_k`. La prueba de convergencia acota ese efecto y muestra que no lo explica
todo: `battery-n1000` converge (0.46 %) y aun así marca 37–38 %, mientras que
`battery-sparse-n250`, también convergido, marca 24.8 %. **La diferencia densa/dispersa es real y
va en el sentido contrario al predicho.** La conjetura de que dispersar aleja el MST de un camino
factible era, sencillamente, incorrecta.

---

## Veredicto

**`MSF_k` está entre 13 % y 29 % por debajo del mejor recorrido construible en las instancias
reales, y corregir esa flojedad no cambia ningún veredicto de la serie: los mueve a todos en la
misma dirección, hacia márgenes más amplios.**

### Lo que queda establecido

1. **La incertidumbre del criterio de relleno de la serie está medida, no supuesta.** 13.3 % en
   `area-27-n72`, 18.6 % en `area-26-n157`, 21.1 % en `area-29-n43` y a lo sumo 28.8 % en
   `reference-n1607`. Las cuatro dentro de la banda 10–30 % que la serie había asumido de la
   literatura. La suposición era correcta.
2. **El umbral de −30 % era conservador, no indulgente.** Su equivalente sobre el ancla alcanzable
   está en [−29.2 %, −16.8 %]. La sospecha de «mover la portería» que el reporte de metrología dejó
   declarada queda refutada en la dirección relevante.
3. **En `area-26-n157` el relleno está agotado.** Los brazos igualan y en 6 filas superan el mejor
   recorrido que sabemos construir. No queda relleno que quitar ahí; lo que queda es el costo de
   recorrer el área. La conclusión que el ciclo de metrología dedujo de una cota inalcanzable se
   sostiene ahora contra un recorrido concreto.
4. **El ancla no respeta `T_max` donde `k` binda**, y eso está reportado, no escondido: 1 tramo de
   3 en `area-26-n157` a k=3, 8 de 25 en la referencia. Empuja hacia el lado conservador —el óptimo
   con restricción está por encima de `UB_k`—, así que ninguna conclusión de arriba se apoya en
   ignorarlo.
5. **El segundo arreglo del instrumento es cuantitativo, no cualitativo.** Corregir de `nn̄` a
   `MSF_k` cambió 14 de 28 veredictos; corregir de `MSF_k` a `UB_k` cambia 0 de 12. **El
   instrumento de la serie convergió.** No hay razón para esperar que un tercer refinamiento del
   cero mueva conclusiones, y ese es el argumento para dejar de refinarlo.

### Adopción

**Ninguna.** Este ciclo no corrió el solver de VRP, no juzgó brazos y no propone cambios. Los
defaults de producción (`spatial_term`, `PenaltyConfig` actual, coeficiente de span espacial 3)
quedan intactos.

`relleno_msf` **sigue siendo la métrica de juicio de la serie**: es la conservadora de las dos, su
cero es una cota demostrada y no depende del presupuesto de cómputo de un TSP. `relleno_ub` queda
disponible como **columna de contexto**, para reportar cuánto de un relleno medido es flojedad de
la cota. Recomendación para ciclos futuros: publicar ambas, juzgar con `relleno_msf`.
