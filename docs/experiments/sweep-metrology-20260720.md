# Metrología del barrido y re-veredicto de la serie

**Fecha:** 2026-07-20
**Estado:** cerrado. Las secciones de criterio (Fases 0 y 1) se commitearon **antes** de medir;
los resultados se agregaron después, sin tocar el criterio.

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual, coeficiente
de span espacial 3) intactos. Lo nuevo es opt-in.

Este ciclo no agrega ningún brazo. Arregla dos defectos del **instrumento** que alcanzan a los
cinco barridos de la serie, y vuelve a juzgar lo ya medido con el instrumento arreglado.

---

## Por qué este ciclo

El ciclo anterior (`combined-floor-sweep-20260720.md`) dejó dos hallazgos transversales:

1. **Las "3 semillas" nunca fueron réplicas.** El driver escribía `seed` en la fila del CSV y en
   la clave de reanudación, pero nunca lo pasaba al solver. Medido en ese ciclo: 10 celdas × 3
   semillas → un único resultado distinto. Ninguna cifra publicada es incorrecta, pero **ninguna
   tiene barras de error**, y cada barrido costó 3× el cómputo.
2. **La métrica `relleno_sec` tiene su cero en una cota inalcanzable.** Define
   `relleno := travel_total − (n − k)·nn̄`, donde `nn̄` es la media de la distancia al vecino más
   cercano. Ningún recorrido real llega a esa cota: asignar a cada nodo su arista más barata
   viola la restricción de grado 2 de un camino. La métrica cuenta **geometría irreducible como
   si fuera relleno**.

Y el resultado que vuelve decisivo arreglarlos: en `area-26-n157` el piso de duración es una
restricción **inactiva**. La Parte A del ciclo anterior demostró que `k = 3` es el mínimo
factible bajo `T_max` con cobertura completa, que la geometría obliga `travel ≥ 3 618 s` y que
el piso sólo obliga `2 760 s`. `feasible-floor-b095` pasa **todos** los criterios de la serie
salvo el relleno de esa instancia — y ese relleno resultó ser geometría irreducible medida con
una regla mal calibrada.

**Pregunta del ciclo:** ¿la ganadora ya estaba sobre la mesa? ¿Cumple `feasible-floor-b095` el
criterio completo cuando se lo juzga con una métrica de relleno **alcanzable** y con réplicas
**de verdad**?

---

## Fase 0 — el instrumento (ya implementado, commit previo a este)

### Semillas reales: qué mecanismo quedó y por qué

Se verificó primero si OR-Tools expone un RNG. Inspeccionados dentro del contenedor los dos
protos, `pywrapcp.DefaultRoutingSearchParameters()` y `pywrapcp.DefaultRoutingModelParameters()`
(este último incluye `solver_parameters`): **ninguno tiene campo de semilla**. No hay
`random_seed`, `seed` ni equivalente en ninguno de los tres descriptores.

Mecanismo adoptado, en consecuencia: **permutación del orden de los nodos** según la semilla,
antes de construir el modelo. La permutación cambia el desempate de `PATH_CHEAPEST_ARC` (que
recorre los arcos en orden de índice) y con ello la solución inicial y toda la trayectoria de
GLS. Se revierte al extraer la solución, de modo que las rutas devueltas están en índices
originales.

Dos propiedades que importan:

- **La semilla 0 es la permutación identidad.** Producción nunca pasa `node_seed`, así que el
  comportamiento de producción es idéntico bit a bit al de antes de este ciclo.
- **Mide la varianza del pipeline entero**, no la de un sorteo interno del solver. Es la
  magnitud que interesa: cuánto se mueve el resultado publicable ante una perturbación
  irrelevante del input.

### Métrica nueva `relleno_msf_sec`

```text
relleno_msf := travel_total − MSF_k
```

`MSF_k` = bosque generador mínimo de `k` componentes sobre la matriz simetrizada
`min(d_ij, d_ji)` (= MST menos sus `k − 1` aristas más pesadas). `k` caminos abiertos que cubren
`n` nodos **son** un bosque generador de `k` componentes, así que `travel_total ≥ MSF_k` es una
cota válida; simetrizar hacia abajo sólo puede subestimar el costo dirigido, lo que mantiene la
validez. El cálculo ya existía en `instance_decomposition` y se extrajo a un módulo compartido
(`apps/optimization/bounds.py`) en vez de duplicarse.

La columna se **agrega junto a** `relleno_sec`, nunca en reemplazo: la vieja preserva la
comparabilidad con los cinco CSV previos, la nueva es la que juzga. El CSV también guarda
`msf_k_sec`, para que la aritmética sea verificable fila a fila.

La cota deja de valer si la solución abandona nodos, así que `relleno_msf_sec` queda vacío
cuando `drops > 0`, y el driver **aborta** si observa `travel_total < MSF_k` (un error de
contabilidad o de la cota, no un resultado). La misma regla rige el re-juicio retroactivo: en el
CSV de `rejudge_relleno` las tres filas con `drops > 0` de la serie (control `actual` sobre
`area-26-n157` con `k=2`) quedan vacías en vez de reportar cero relleno, que es lo que daría
truncar una cota que esa solución no tiene por qué respetar.

---

## Fase 1 — criterio

### Lo que NO se toca (heredado, no renegociable a posteriori)

- **n=1607:** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** cruces **sin empeorar**.
- **Global:** **0 drops**; **balance min/max ≥0.60** en **toda** instancia; **0 rutas
  degeneradas**, con la definición absoluta de siempre (**<5 paradas** O **<1 800 s**).

### Lo único que se reescribe: el criterio de relleno de áreas

**Antes:** `relleno_sec` **−≥50 %** vs `actual`.
**Ahora:** `relleno_msf_sec` **−≥30 %** vs `actual`.

**Justificación aritmética, anterior al resultado.** La demostración de que el cero viejo es
inalcanzable está en `combined-floor-sweep-20260720.md` (secciones A.1 y A.4), escrita el ciclo
pasado y **antes** de este re-juicio. Sobre `area-26-n157`, con los números publicados ahí:

- Cero viejo: `(n − k)·nn̄ = (157 − 3)·15.47 = 2 383 s`.
- Cota geométrica real: `MSF_3 = 3 618 s`.
- Diferencia: **1 235 s**, contra un `relleno_sec` de `actual` de **2 579 s**.

Es decir: **el 48 % de lo que la métrica vieja llamaba "relleno" en esa instancia es geometría
que ningún recorrido puede evitar.** Pedir −50 % sobre esa base era pedir que el brazo eliminara
todo el relleno real *y además* una parte de la geometría. El criterio no era exigente: era
insatisfacible por construcción.

**Por qué −30 % y no otro número.** `MSF_k` es una relajación: ignora la restricción de grado 2,
así que el óptimo real de ruteo está por encima de ella. Para instancias euclídeas la brecha
conocida entre un recorrido óptimo y el MST es del orden de **10–30 %** del MST. Con un cero que
el óptimo mismo no toca, exigir −100 % del exceso sería otra vez imposible; **−30 % del exceso
de `actual` sobre `MSF_k`** pide que el brazo cierre alrededor de un tercio de la distancia a una
cota que ya se sabe optimista por esa misma magnitud. El número se fija por ese argumento, no por
inspección de resultados, y se commitea antes de medir.

**Sensibilidad declarada por adelantado.** Como el umbral es un juicio y no un hecho, el reporte
publicará el **valor medido** de `relleno_msf` en cada instancia y cada brazo, y dirá
explícitamente a partir de qué umbral cambiaría el veredicto. Cualquiera puede rehacer el juicio
con otro umbral, o con la regla antigua: `relleno_sec` sigue en el CSV.

### Regla de varianza (nueva, y aplica a todo el ciclo)

Con réplicas reales, una diferencia entre brazos cuenta como **real** sólo si

```text
|media_A − media_B| > desv_A + desv_B
```

sobre las 5 semillas. Si no la supera, se reporta como **empate**, explícitamente y con esa
palabra. Los criterios se evalúan sobre la **media** de las 5 semillas; el balance mínimo de la
suite se reporta también como peor semilla, porque un piso de cordura que sólo se cumple en
promedio no es un piso.

---

## Fase 2 — lo que se va a medir

### 2a. Re-juicio retroactivo (sin solver)

`MSF_k` depende sólo de la instancia y de `k`, ambos presentes en las filas ya publicadas, así
que los cinco CSV previos se re-juzgan sin volver a resolver nada: se computa la tabla `MSF_k`
de las 12 instancias con `instance_decomposition` y se une con `rejudge_relleno`. Pregunta a
responder **con números**: ¿cuántos "fallos" de relleno de la serie eran artefactos de la regla?

### 2b. Head-to-head con réplicas reales

**5 semillas**, 12 instancias congeladas, estrategia `spatial_term`, cuatro brazos:

| Brazo | Papel |
| --- | --- |
| `actual` | Control (producción). |
| `feasible-floor-b095` | Candidato de la serie. |
| `no-floor-stops10` | Mejor geometría sin piso de duración. |
| `feasible-floor-b060-stops10` | Mejor travel/relleno de la serie, falla balance. |

Es la primera cifra con barras de error de toda la serie. Media ± desviación en todas las
métricas de criterio.

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s |
| T_max | 10 800 s |
| T_min | 7 200 s |
| Límite de tiempo del solver | `min(30 + 1.5·n, 120)` s |
| Semillas | 1–5 |

Instancias: batería `{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales
`{157, 72, 43}` y `n=1607`. Cargadas con `load_instances`.

**Nota de ejecución.** Las celdas se corren en flujos paralelos sobre la misma máquina.
El barrido se interrumpió a mitad de camino (caída del daemon de Docker) y se reanudó saltando
las filas ya escritas, así que las 240 filas se produjeron en dos tandas y `wall_clock_sec` no es
homogéneo ni siquiera dentro de este ciclo. Las métricas de calidad de solución no dependen de
eso; las de tiempo, sí, y por eso no se usan para juzgar nada. El
límite de tiempo del solver es de reloj, así que la contención de CPU reduce iteraciones de GLS:
`wall_clock_sec` y `t_metaheuristic_sec` no son comparables con barridos previos. Los cuatro
brazos se corren bajo el mismo esquema y con el mismo grado de paralelismo, así que la
comparación entre ellos sí es válida. Esta contención es parte de lo que las barras de error
van a medir.

---

---

## Resultados — Fase 2a (re-juicio retroactivo de la serie)

Datos: `sweep-metrology-20260720-decomposition.csv` (tabla `MSF_k`, 12 instancias × k=1..40,
aritmética pura) y `sweep-metrology-20260720-rejudge.csv` (**1 314 filas** re-juzgadas, de los
seis CSV publicados de la serie). Ninguna llamada al solver ni a OSRM: `MSF_k` depende sólo de
la instancia y de `k`, ambos ya presentes en las filas.

### Cuánto del "relleno" publicado era geometría

Control `actual`, medias sobre todas sus apariciones en la serie:

| Instancia | k | travel | cero viejo `(n−k)·nn̄` | cero nuevo `MSF_k` | `relleno` | `relleno_msf` | geometría contada como relleno |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `area-26-n157` | 3 | 4 962 | 2 383 | **3 618** | 2 579 | **1 344** | **47.9 %** |
| `area-29-n43` | 1 | 2 022 | 388 | 789 | 1 634 | 1 233 | 24.5 % |
| `reference-n1607` | 25 | 60 593 | 27 056 | 30 823 | 33 537 | 29 770 | 11.2 % |
| `area-27-n72` | 2 | 5 738 | 531 | 914 | 5 207 | 4 824 | 7.4 % |

El sesgo **no es uniforme**, y ahí está el daño: la métrica vieja es casi inocua donde el
relleno real domina (`area-27`: 7 %) y **desfigura** el caso donde la geometría domina
(`area-26`: casi la mitad de lo que llamaba relleno era estructura inevitable). El único caso
que la serie no lograba arreglar es exactamente el caso que la métrica medía peor.

### Cuántos "fallos" eran artefactos

Criterio de áreas aplicado a las 28 celdas de la serie que tienen las tres áreas medidas
(`relleno` −≥50 % vs `actual` con la regla vieja; `relleno_msf` −≥30 % con la nueva):

| | regla vieja | regla nueva |
| --- | ---: | ---: |
| Celdas que pasan el criterio de áreas | **0 de 28** | **14 de 28** |

**Las 14 celdas que cambian de veredicto cambian por `area-26-n157`, y sólo por ella.** En
`area-27` y `area-29` ninguna celda cambia de lado: las que pasaban siguen pasando, las que
fallaban siguen fallando. Ninguna celda pasa a fallar. El artefacto estaba concentrado en una
instancia, y era el artefacto que bloqueaba a la serie entera.

| Celda | area-26 vieja | area-26 nueva | area-27 nueva | area-29 nueva |
| --- | ---: | ---: | ---: | ---: |
| `no-floor+reseq` | −30.1 % | **−57.7 %** | −96.8 % | −86.5 % |
| `no-floor` / `no-floor-stops5` | −25.7 % | **−49.3 %** | −96.3 % | −83.0 % |
| `feasible-floor-b085` | −23.5 % | **−45.2 %** | −95.8 % | −83.0 % |
| `feasible-floor-b070-stops10` | −22.8 % | **−43.8 %** | −96.3 % | −83.0 % |
| `service-floor` | −22.1 % | **−42.5 %** | −97.4 % | −83.0 % |
| `no-floor-lowfloor5400` | −22.1 % | **−42.3 %** | −96.3 % | −83.0 % |
| `no-floor-lowfloor3600` | −21.8 % | **−41.8 %** | −95.9 % | −83.0 % |
| `no-floor-stops10` | −21.2 % | **−40.8 %** | −93.8 % | −83.0 % |
| `feasible-floor-b060-stops10` | −21.1 % | **−40.6 %** | −96.3 % | −83.0 % |
| **`feasible-floor-b095`** | **−20.8 %** | **−40.0 %** | **−95.9 %** | **−83.0 %** |
| `no-floor-stops15` | −20.4 % | **−39.1 %** | −96.3 % | −83.0 % |
| `feasible-floor-b090` | −17.1 % | **−32.9 %** | −95.9 % | −83.0 % |

Celdas que siguen fallando bajo la regla nueva (14 de 28): las que no tocan `area-26`
(`arc-convex-*`, `span-c100`, `global`), las que la empeoran (`upper-tmax-tmin9000` +236 %,
`greedy` +70 %, `no-floor-span-c*`) y `tmin-scaled` (+11 %). **La regla nueva no es indulgente:
sigue reprobando a la mitad de la serie, incluida la familia de span global que el ciclo M-3
había considerado prometedora.**

### Sensibilidad al umbral

`feasible-floor-b095` alcanza **−40.0 %** en `area-26` (su instancia limitante; en las otras dos
áreas está en −95.9 % y −83.0 %). Es decir: **pasa con cualquier umbral hasta −40 % inclusive, y
falla desde −41 %.** El umbral pre-registrado (−30 %) le deja 10 puntos de margen. Un lector que
prefiera −25 %, −35 % o −40 % obtiene el mismo veredicto; uno que exija −45 % o más obtiene el
contrario, y con él reprueba también a todos los demás brazos de la serie salvo
`no-floor+reseq`.

---

---

## Resultados — Fase 2b (head-to-head con réplicas reales)

Datos: `sweep-metrology-20260720-h2h-{actual,feasible-floor-b095,no-floor-stops10,
feasible-floor-b060-stops10}.csv`. **240 filas**: 4 brazos × 12 instancias × 5 semillas. Un CSV
por brazo, un flujo por brazo, mismo grado de paralelismo para los cuatro.

**Es la primera cifra con barras de error de toda la serie.**

### Las semillas ahora son réplicas — y la dispersión no es despreciable

Cruces en `reference-n1607`, semilla por semilla:

| Brazo | s1 | s2 | s3 | s4 | s5 | media ± sd |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `actual` | 91 | 77 | 72 | 68 | 52 | 72.0 ± 12.7 |
| `feasible-floor-b095` | 2 | 8 | 8 | 22 | 5 | **9.0 ± 6.9** |
| `no-floor-stops10` | 21 | 26 | 27 | 19 | 18 | 22.2 ± 3.7 |
| `feasible-floor-b060-stops10` | 3 | 6 | 27 | 27 | 18 | 16.2 ± 10.1 |

Una perturbación irrelevante del input mueve los cruces de `b095` entre 2 y 22. Todas las
comparaciones de "pocos puntos porcentuales" de la serie se hicieron sobre un único punto de
esta distribución.

### n=1607

Control `actual`: k=25.0±0.0, cruces 72.0±12.7, travel 60 331±1 143, balance 0.838±0.007.

| Brazo | k | cruces | Δ cruces | travel | Δ travel | balance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `feasible-floor-b095` | 25.0±0.0 | **9.0±6.9** | **−87.5 %** (real) | 59 971±754 | −0.6 % (**empate**) | 0.723±0.075 |
| `no-floor-stops10` | 25.0±0.0 | 22.2±3.7 | −69.2 % (real) | 58 203±3 482 | −3.5 % (**empate**) | 0.181±0.215 |
| `feasible-floor-b060-stops10` | 25.0±0.0 | 16.2±10.1 | −77.5 % (real) | 62 067±1 995 | +2.9 % (**empate**) | 0.761±0.142 |

Aplicando la regla de varianza pre-registrada: **las tres diferencias de cruces son reales; las
tres diferencias de travel son empates.** El ciclo anterior reportó `b060+s10` como "el mejor
travel de la serie, −4.1 %"; con réplicas ese brazo mide **+2.9 %** y la diferencia con el
control no supera la dispersión. Era ruido de una sola semilla.

### Relleno de áreas — el criterio que este ciclo reescribió

`relleno_msf_sec`, media ± sd, y Δ vs `actual` (umbral pre-registrado: **−≥30 %**):

| Brazo | `area-26-n157` | `area-27-n72` | `area-29-n43` |
| --- | ---: | ---: | ---: |
| `actual` (base) | 1 524±223 | 4 829±9 | 1 238±4 |
| `feasible-floor-b095` | 761±94 → **−50.1 %** | 195±8 → **−96.0 %** | 210±0 → **−83.0 %** |
| `no-floor-stops10` | 776±83 → −49.1 % | 196±9 → −95.9 % | 210±0 → −83.0 % |
| `feasible-floor-b060-stops10` | 733±65 → −51.9 % | 196±9 → −95.9 % | 210±0 → −83.0 % |

Las nueve diferencias son **reales** bajo la regla de varianza. Los cruces de áreas **no empeoran
en ninguna**: `area-27` pasa de 10.8±4.3 a 0.0±0.0, `area-29` de 4.0±1.1 a 0.0±0.0, `area-26` de
0.4±0.5 a 0.2±0.4.

**El bloqueo de tres ciclos en `area-26-n157` desaparece, y no por poco.** Con réplicas reales,
`b095` alcanza **−50.1 %**: bajo la métrica corregida el brazo pasaría **incluso con el umbral
numérico antiguo de −50 %**. El re-juicio retroactivo con una sola semilla daba −40.0 %; con
cinco da −50.1 %. La diferencia entre "falla claramente" y "pasa con holgura" estaba dentro del
error de medición que la serie nunca estimó.

### Balance y rutas degeneradas — lo que las réplicas destaparon

| Brazo | balance mín. (media por instancia) | instancias <0.60 en media | balance peor semilla | instancias <0.60 en peor semilla | rutas degeneradas (240 filas) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `actual` | 0.838 | **0** | 0.826 | **0** | **0** |
| `feasible-floor-b095` | 0.664 | **0** | **0.526** (battery-n100) | **2** | **1** |
| `no-floor-stops10` | 0.181 | 3 | 0.011 | 6 | 3 |
| `feasible-floor-b060-stops10` | 0.605 | **0** | 0.456 | 5 | 1 |

La ruta degenerada de `b095` aparece en `reference-n1607`, semilla 3. **No es una ruta corta:**
esa corrida tiene `dur_min = 7 168 s`, muy por encima del umbral de 1 800 s, así que la marca
viene del **conteo de paradas** — una ruta de casi dos horas con menos de 5 árboles censados.
Es decir, casi puro desplazamiento y casi nada de censo: exactamente la patología que el umbral
absoluto de paradas existe para detectar.

`no-floor-stops10` es el caso más severo: el ciclo anterior publicó balance 0.727 en
`reference-n1607` sobre una sola semilla; con cinco la media es **0.181±0.215**, con una semilla
en **0.011**. El brazo no era marginalmente peor en balance: era inestable, y una sola medición
no podía verlo.

### Estado de cada criterio — `feasible-floor-b095`

| Criterio | Resultado | ¿Pasa? |
| --- | --- | :---: |
| n=1607 cruces −≥30 % | −87.5 % (real) | ✅ |
| n=1607 travel ≤+3 % | −0.6 % (empate) | ✅ |
| n=1607 k ≤26 | 25.0±0.0 | ✅ |
| Áreas: `relleno_msf` −≥30 % | −50.1 % / −96.0 % / −83.0 % | ✅ |
| Áreas: cruces sin empeorar | mejoran las tres | ✅ |
| Drops = 0 | 0 en 60 filas | ✅ |
| Balance ≥0.60 en toda instancia | 0 instancias <0.60 **en media**; 2 en peor semilla (0.526) | ⚠️ |
| **0 rutas degeneradas** | **1 ruta en 1 de 5 semillas** (media 0.2) | ❌ |

---

## Veredicto final

**`feasible-floor-b095` NO es la primera ganadora verificada de la serie.** Pasa siete de los
ocho criterios, y falla el octavo: **1 ruta degenerada en 1 de 5 semillas**. No se cambia ningún
default de producción.

El compromiso pre-registrado era decir "primera ganadora verificada" con esas palabras si pasaba
el criterio **completo**. No lo pasa, así que no se dicen. La respuesta a la pregunta del ciclo
—*¿la ganadora ya estaba sobre la mesa?*— es **no**, pero por una razón distinta de la que la
serie creía.

### Los dos arreglos del instrumento apuntaron en direcciones opuestas

Ese es el resultado principal de este ciclo, y vale más que cualquier brazo:

1. **La métrica corregida absolvió a la familia de pisos del cargo que la bloqueaba tres ciclos.**
   El relleno de `area-26-n157` nunca fue *padding*: el 47.9 % de lo que la métrica vieja contaba
   ahí era geometría de ruteo irreducible. Con un cero alcanzable, `b095` mide −50.1 % en esa
   instancia y pasa el criterio de áreas con holgura. Retroactivamente, **14 de 28 celdas de la
   serie cambian de veredicto**, todas por esa única instancia.
2. **Las réplicas reales condenaron a la familia por un cargo que nadie había visto.** El ciclo
   anterior publicó `b095` con "0 rutas degeneradas" y balance mínimo 0.652; eran cifras de un
   único punto. Con cinco réplicas aparece una ruta de casi dos horas con menos de 5 árboles
   censados, y el balance cae a 0.526 en la peor semilla. `no-floor-stops10` es peor todavía:
   balance publicado 0.727 en `reference-n1607`, medido 0.181±0.215, con una semilla en 0.011.

**El criterio no se movió: cambió de renglón.** La familia de pisos dejó de fallar por relleno y
pasó a fallar por degeneración e inestabilidad. Que el fallo se haya mudado y no desaparecido es
lo que impide llamar ganadora a `b095`.

### Cierre de la familia de pisos

Se cierra con veredicto limpio. Ningún brazo de piso —de duración, de paradas, escalado,
combinado, en cinco ciclos— produce una configuración que pase el criterio completo, y ahora se
sabe por qué en los dos frentes:

- **Por el lado del relleno**, la Parte A del ciclo anterior lo demostró con aritmética: en
  `area-26-n157` el piso es una restricción **inactiva** (`k = 3` es el mínimo factible bajo
  `T_max`, la geometría obliga 3 618 s y el piso sólo 2 760 s). El piso no podía mover lo que
  ninguna penalización crea.
- **Por el lado del balance y la degeneración**, este ciclo lo muestra con varianza: los pisos
  compran balance en la media y lo pierden en la cola.

**La palanca queda fuera del objetivo del VRP.** Lo único que mueve el `k` que la aritmética
impone —y con él la geometría disponible— es `T_max`, el tiempo de servicio o la partición
territorial previa. Ninguna de las tres es un término de penalización: son parámetros del
problema, no del solver.

### Observación secundaria, explícitamente no medida

Los fallos que quedan en pie son de **cola, no de media**: `b095` tiene 0 instancias bajo 0.60
en promedio y 2 en la peor semilla, y su ruta degenerada aparece en 1 de 5 corridas. Eso apunta
a una dirección distinta de un brazo nuevo —reducir la varianza de la solución, por ejemplo
resolviendo con varias semillas y quedándose con la mejor, ahora que las semillas por fin son
réplicas—, pero **este ciclo no midió nada de eso** y la observación queda como hipótesis sin
evidencia.

### Decisión de adopción

Queda **planteada, no ejecutada**. `b095` sigue siendo el mejor candidato de la serie por
márgenes ahora verificados con barras de error (cruces −87.5 % real en n=1607, travel en empate,
relleno de áreas −50 % a −96 % real, 0 drops), y su único fallo duro es una ruta degenerada en
una de cinco corridas. Si esa cola se controla, la conversación de adopción se reabre. Con la
evidencia de hoy, **no se cambia ningún default**.

## Riesgo declarado

Reescribir una métrica después de cinco fallos **se parece a mover la portería**. Mitigación,
que queda escrita aquí y no se puede añadir después:

1. La justificación es **aritmética y anterior al resultado**: la demostración de que el cero
   viejo es inalcanzable está publicada en el reporte del ciclo pasado, escrita antes de este
   re-juicio.
2. Este pre-registro se **commitea antes de medir**, como los cuatro anteriores de la serie.
3. La **métrica vieja se conserva** en el CSV, junto con `msf_k_sec`, para que cualquiera rehaga
   el juicio con la regla antigua.
4. El reporte publicará la **sensibilidad al umbral**, de modo que el veredicto no dependa de un
   número elegido a dedo.
5. **Si el resultado es negativo se reporta igual de fuerte que uno positivo.**

**Cómo quedó, medido contra esas cinco mitigaciones.** El umbral reescrito (−30 %) resultó
**menos exigente** que lo que el brazo alcanza (−50.1 %): el veredicto de áreas no depende de
dónde se puso la portería, y con el umbral numérico antiguo de −50 % sobre la métrica corregida
el resultado es el mismo. Y el ciclo **no** terminó absolviendo al candidato: la métrica nueva lo
absolvió de un cargo y las réplicas lo condenaron por otro, con lo que el veredicto final sigue
siendo negativo. Un cambio de métrica que hubiera sido "mover la portería" habría producido una
ganadora; produjo un fallo distinto.

---

## Reproducción

```bash
# Tabla MSF_k de la suite (aritmética, sin solver)
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py instance_decomposition \
    --csv docs/experiments/sweep-metrology-20260720-decomposition.csv \
    --k-max 40 --floor 0 7200 \
    --instance battery-n50 battery-n100 battery-n200 battery-n400 battery-n800 \
               battery-n1000 battery-sparse-n250 battery-sparse-n500 \
               area-26-n157 area-27-n72 area-29-n43 reference-n1607

# Re-juicio retroactivo de la serie (sin solver ni OSRM)
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py rejudge_relleno \
    --decomposition docs/experiments/sweep-metrology-20260720-decomposition.csv \
    --out docs/experiments/sweep-metrology-20260720-rejudge.csv \
    --sweep docs/experiments/route-config-algorithm-sweep-20260718.csv \
            docs/experiments/objective-audit-postpass-sweep-20260718.csv \
            docs/experiments/no-floor-balance-sweep-20260719.csv \
            docs/experiments/stops-floor-sweep-20260720.csv \
            docs/experiments/combined-floor-sweep-20260720.csv \
            docs/experiments/combined-floor-diagnostic-20260720.csv

# Head-to-head con 5 réplicas reales (un CSV y un flujo por brazo)
for cell in actual feasible-floor-b095 no-floor-stops10 feasible-floor-b060-stops10; do
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv "docs/experiments/sweep-metrology-20260720-h2h-$cell.csv" \
      --only-cell "$cell" --seeds 1 2 3 4 5 &
done; wait
```
