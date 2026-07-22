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

```
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

```
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

```
Δ%  =  (travel_arm − travel_actual) / (travel_actual − ancla)
```

El numerador **no depende del ancla**. El denominador sí, y como `UB_k > MSF_k`, el denominador
bajo el ancla alcanzable es **más chico**. Por lo tanto:

> **Predicción pre-registrada 1.** Para todo brazo que mejore el relleno respecto de `actual`,
> `|Δ%|` medido contra `UB_k` será **mayor o igual** que medido contra `MSF_k`. Es decir: el ancla
> alcanzable es **más indulgente**, y el criterio anclado en `MSF_k` es el **conservador** de los
> dos.

> **Predicción pre-registrada 2.** En consecuencia, ninguna celda que **pasaba** bajo `MSF_k` puede
> **fallar** bajo `UB_k` (con `k` igual). Los únicos cambios de veredicto posibles son
> fallo → aprobación. Si se observa un cambio aprobación → fallo, la causa sólo puede ser un `k`
> distinto entre brazos, y se investigará y reportará como tal.

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
