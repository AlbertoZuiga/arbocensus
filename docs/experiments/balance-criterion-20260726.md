# Desdoblamiento del criterio de balance: reparto vs aceptabilidad operativa

**Fecha:** 2026-07-26
**Estado:** pre-registro. Este documento se commitea **antes** de correr una sola celda. Los
resultados se agregan después, sin tocar el criterio.

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual, coeficiente de
span espacial 3, post-pass 2-opt activo) intactos. Lo nuevo es opt-in.

---

## 1. Motivación

El brazo `no-floor-stops10` (`config_algorithm_sweep.py:159`) quedó registrado en la serie como
*el mejor brazo en travel que muere sólo por el criterio de balance*. Esa lectura no se sostiene
contra los datos en disco. Tres observaciones, verificadas fila a fila antes de escribir este
pre-registro.

### 1.1 El travel del brazo está confundido con la ruta degenerada

`docs/experiments/sweep-metrology-20260720-h2h-no-floor-stops10.csv`, filas 57–61
(`instance = reference-n1607`, semillas reales), contra el control de la misma corrida
(`sweep-metrology-20260720-h2h-actual.csv`, mismas semillas):

| semilla | travel `stops10` | travel `actual` | Δ travel | balance | `dur_min_sec` | `degenerate_routes` |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 55 954 | 61 269 | **−8,7 %** | 0,011 | **120** | 1 |
| 2 | 55 592 | 61 387 | **−9,4 %** | 0,011 | **120** | 1 |
| 3 | 62 949 | 60 042 | **+4,8 %** | 0,346 | 3 710 | 0 |
| 4 | 61 881 | 58 253 | **+6,2 %** | 0,524 | 5 644 | 0 |
| 5 | 54 641 | 60 702 | **−10,0 %** | 0,011 | **120** | 1 |

El −8,7 % citado es la semilla 1. **Las tres semillas de mejor travel son exactamente las tres
que producen una ruta de 120 segundos**, y las dos semillas sin ruta degenerada empeoran el
travel respecto del control. Agrupando: semillas con stub, travel medio 55 396 s contra 61 119 s
del control (−9,4 %); semillas sin stub, 62 415 s contra 59 148 s (**+5,5 %**). El signo de la
ventaja de travel se invierte según haya o no ruta degenerada. La ganancia no es geometría más
barata: es un árbol al que se le quitó la jornada.

### 1.2 La medición que no veía el stub usaba semillas falsas

`docs/experiments/stops-floor-sweep-20260720.csv`, mismo brazo con `spatial_span_coef = 3`:

| semilla | travel | balance | `dur_min_sec` | `degenerate_routes` |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 58 330 | 0,727 | 7 835 | 0 |
| 2 | 58 413 | 0,727 | 7 835 | 0 |
| 3 | 58 288 | 0,727 | 7 835 | 0 |

Tres valores de balance y `dur_min` **idénticos al segundo**: son las semillas anteriores al fix
de metrología, que el driver escribía en el CSV pero nunca pasaba al solver
(`sweep-metrology-20260720.md`, «Por qué este ciclo», punto 1). En el mismo CSV las tres filas de
`spatial_span_coef = 30` son idénticas dígito a dígito (61 182 / 0,011 / 120), lo que confirma la
ausencia de réplica. Esa corrida única cayó en una región sin stub y publicó `dur_min = 7 835 s`,
0 degeneradas y balance 0,727 — el retrato favorable del brazo proviene de una sola muestra
afortunada de una distribución que va de 120 s a 5 644 s.

### 1.3 El brazo nunca se midió bajo los defaults de hoy

Las dos mediciones anteriores llevan `post_resequence = False`. El post-pass 2-opt es desde
`postpass-default-20260724.md` un paso incondicional del pipeline de producción
(`pipeline.py:218`), con mejora de Pareto medida en 12/12 instancias (travel −16,2 % de media,
`crossings_road` −18,6 %). **Ninguna cifra publicada de este brazo existe bajo la configuración
que hoy corre en producción.** El post-pass reordena la secuencia dentro de cada ruta sin
redistribuir árboles, así que no puede por sí solo crear ni destruir una ruta de 120 s; lo que sí
puede es mover el travel de todos los brazos y con ello el tamaño de la diferencia que se está
midiendo.

### 1.4 Nota sobre el instrumento: el driver no aplica el default de producción

Verificado antes de medir: el driver gatea el post-pass en `cell.post_resequence`
(`config_algorithm_sweep.py:704`), que por defecto es `False` y no tenía flag de CLI. Es decir,
el barrido no heredaba el default de producción y habría vuelto a medir sin post-pass, que es
justamente el defecto 1.3. Este ciclo agrega la opción `--post-resequence` para forzarlo en todas
las celdas de la corrida; queda registrada en la columna `post_resequence` del CSV, que ya forma
parte de la clave de reanudación, así que no colisiona con filas históricas. Ninguna definición de
celda cambia y el default del driver sigue siendo `False`, de modo que los CSV previos siguen
siendo reproducibles.

---

## 2. Objetivo del ciclo

Decidir, con medición propia bajo los defaults actuales, si el criterio de balance debe
**desdoblarse**, y si algún brazo que hoy muere sólo por balance sobrevive la lectura operativa.

### El desdoblamiento que se pre-registra

| criterio | definición | estado |
| --- | --- | --- |
| **Operativo** | **0 rutas degeneradas**, degenerada = duración **< 1 800 s**. Sólo duración, sin condición de conteo de paradas. | **No se relaja.** |
| **De reparto** | **balance ≥ 0,60** en toda instancia. | **En discusión.** |

**Razón del desdoblamiento.** Es una decisión de producto tomada el 2026-07-19 y anterior a este
ciclo: el balance *dentro* de un dataset es sacrificable, porque el balance que le importa a un
censista es de largo plazo y se consigue por **asignación** de rutas a lo largo de semanas, no
igualando las rutas de un único corte territorial. El criterio operativo no es sacrificable por la
razón simétrica: una ruta de 120 segundos no es la jornada de nadie, y ninguna política de
asignación la arregla.

Los dos criterios se separan porque miden cosas distintas que el criterio único confundía:
«las rutas duran parecido» y «cada ruta es una jornada entregable». La segunda es una cota
inferior por ruta; la primera es una razón entre rutas. Un brazo puede fallar la primera y cumplir
la segunda, y sólo en ese caso el desdoblamiento cambia un veredicto.

El driver ya publica las dos lecturas por separado: `degenerate_routes` cuenta sólo por duración
y el conteo de paradas va aparte en `short_routes` (`config_algorithm_sweep.py:898-900`). Esa
columna **no es comparable** con la de los CSV anteriores al cambio, que combinaba ambas
condiciones — motivo adicional por el que la línea base se re-corre aquí en vez de releerse.

---

## 3. Diseño

### Celdas

| Celda | Papel |
| --- | --- |
| `actual` | Línea base, **re-corrida dentro de este ciclo**. Obligatorio: la varianza entre corridas supera la varianza entre semillas de una misma corrida. |
| `no-floor-stops10` | El brazo en discusión. |
| `no-floor-stops15` | Responde si el stub es propio de `stops10` o de toda la familia sin piso de duración. |

Las tres con `--post-resequence`, estrategia `spatial_term`, penalidad de piso de paradas en su
default (10 000).

### Instancias

Las 12 congeladas de `INSTANCES` (`config_algorithm_sweep.py:83`): batería
`{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales `{157, 72, 43}` y
`reference-n1607`. Cargadas con `load_instances` (UUID estables, la cache OSRM acierta). No se
inventa ninguna instancia nueva.

### Semillas

**3 semillas reales** (1, 2, 3): la semilla permuta el orden de los nodos antes de construir el
modelo, porque OR-Tools no expone RNG. **Comprobación obligatoria antes de interpretar nada:** si
las réplicas de una celda devuelven valores idénticos al segundo, las semillas no llegaron al
solver y el cómputo es basura — es el defecto 1.2, y no se puede volver a publicar sobre él.

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s |
| T_max | 10 800 s |
| T_min | 7 200 s (sólo lo usan los brazos que lo declaran) |
| Límite de tiempo del solver | `min(30 + 1.5·n, 120)` s |
| Post-pass 2-opt | **activo** (default de producción) |

Costo: 3 celdas × 12 instancias × 3 semillas = **108 corridas**, ~3,6 h de reloj. Se lanza en
background y no se interrumpe.

**Nota de ejecución, declarada por adelantado.** Otro worktree corre un barrido en paralelo sobre
la misma máquina (~1 core de 12) y comparte la db y OSRM. El límite de tiempo del solver es de
reloj, así que `wall_clock_sec` y `t_metaheuristic_sec` no son comparables con barridos previos y
no se usan para juzgar nada. Las tres celdas corren bajo el mismo esquema, así que la comparación
entre ellas es interna y homogénea.

---

## 4. Predicciones (escritas antes de correr)

### 4.1 Predicción principal, falsable

**`no-floor-stops10` falla el criterio OPERATIVO en `reference-n1607`:** al menos una de las 3
semillas presenta `dur_min_sec < 1 800`. Y **su ventaja en travel desaparece o se invierte en las
semillas sin ruta degenerada**: el Δ travel medio contra `actual` restringido a las semillas con
`degenerate_routes = 0` es ≥ 0 %, o bien no supera la suma de las desviaciones.

**Si se cumple, desdoblar el criterio NO rescata al brazo**, porque el brazo no muere por reparto:
muere por la lectura que el desdoblamiento declara irrenunciable. En ese caso el hallazgo se
publica como limitación, y el desdoblamiento queda como una aclaración de criterio que no cambia
ningún veredicto de la serie.

**Qué la falsaría:** las 3 semillas con `dur_min_sec ≥ 1 800` en `reference-n1607`, con una
ventaja de travel que sobreviva la regla de varianza. Eso convertiría al brazo en candidato real y
al desdoblamiento en la decisión que lo habilita.

### 4.2 Predicción secundaria

`no-floor-stops15` muestra el **mismo** patrón que `stops10` (stub en al menos una semilla de
`reference-n1607`), porque el mecanismo sospechado no es la altura del piso de paradas sino la
ausencia de piso de **duración**: 15 paradas juntas y compactas siguen pudiendo durar mucho menos
que media mañana, y nada en el objetivo prohíbe la ruta corta. Si en cambio `stops15` sale limpio
en las 3 semillas, el problema es de altura del piso y no de familia, y eso reabre la familia por
una puerta distinta.

### 4.3 Comprobación de cordura del instrumento

La celda `actual` sobre `reference-n1607` debe reproducir, en las 3 semillas:

- **k = 25**
- **`drops` = 0**
- **`degenerate_routes` = 0** (ninguna ruta bajo 1 800 s)

Es el comportamiento de producción, conocido por construcción y verificado en cinco barridos
previos. **Si esto falla, la implementación está mal y no hay nada que interpretar**: el ciclo se
detiene y se reporta el fallo del instrumento, no un veredicto sobre los brazos.

---

## 5. Criterio de aceptación a priori

Heredado de la serie y **no renegociable a posteriori**.

| # | Criterio | Umbral |
| --- | --- | --- |
| 1 | `reference-n1607` auto-cruces | **−30 % o mejor** vs `actual` |
| 2 | `reference-n1607` travel | **≤ +3 %** vs `actual` |
| 3 | `reference-n1607` flota | **k ≤ 26** |
| 4 | Áreas (157/72/43) relleno | **`relleno_msf_sec` −30 % o mejor** vs `actual` |
| 5 | Áreas auto-cruces | **sin empeorar** |
| 6 | Global | **`drops` = 0** |
| 7 | **Reparto** | **balance ≥ 0,60** en toda instancia |
| 8 | **Operativo** | **0 rutas degeneradas por duración** (`degenerate_routes` = 0) |

**Se reportan SIEMPRE las dos lecturas: con y sin el ítem 7.** Es el objeto del ciclo, y por eso
la tabla de veredictos llevará dos columnas de resultado por brazo.

**Métrica de auto-cruces.** Se juzga sobre **`crossings_road`** (polilínea real de OSRM).
`crossings_chord` se reporta al lado, por continuidad con la serie, pero no juzga: la correlación
de rangos entre las dos es 0,527 y está **invertida** en `reference-n1607`
(`crossing-metric-validation-20260723.md`). Esta elección se fija aquí, antes de ver los números.

**Regla de varianza.** Una diferencia entre brazos cuenta como **real** sólo si

```text
|media_A − media_B| > desv_A + desv_B
```

sobre las 3 semillas. Si no la supera se reporta como **empate**, con esa palabra. Los criterios
se evalúan sobre la media de las 3 semillas; balance mínimo y degeneración se reportan **además**
como peor semilla, porque un piso que sólo se cumple en promedio no es un piso.

---

## 6. Qué salidas son publicables

**El resultado negativo se publica igual de fuerte que uno positivo.** Este pre-registro se
commitea antes de medir precisamente para que el veredicto no dependa de lo que salga. Los tres
desenlaces están comprometidos por escrito:

1. **La predicción principal se cumple** → el desdoblamiento no rescata al brazo; se publica como
   limitación y trabajo futuro, y no se cambia ningún default.
2. **La predicción principal se falsa** → el brazo pasa el criterio operativo y el desdoblamiento
   sí cambia su veredicto; se publica como propuesta verificada, y la decisión de adopción se
   plantea con sus números, sin ejecutarla en este ciclo.
3. **La comprobación de cordura falla** → se publica el fallo del instrumento y ningún veredicto
   sobre brazos.

Se reportan **todas** las celdas y todas las instancias, no las que ganan. Elegir la mejor celda
a posteriori y presentarla como si hubiera sido la hipótesis invalida el ciclo entero.

---

## 7. Alcance — qué NO hace este ciclo

- **No toca ningún default de producción.** Ni el `PenaltyConfig`, ni la estrategia, ni el
  post-pass. Todo brazo nuevo es un override de CLI.
- **No toca el solver.** No se agregan dimensiones, penalizaciones ni callbacks.
- **No recalibra `spatial_span_coef`.** Queda en 3 en las tres celdas. Su grilla ya se midió y el
  3 quedó confirmado (`stops-floor-sweep-20260720.md`, «Grilla de span espacial»).
- **No reabre la familia de pisos de duración.** `feasible-floor-*`, `lowfloor*` y los pisos
  combinados quedan fuera; la familia se cerró con veredicto en
  `sweep-metrology-20260720.md` y aquí no se re-litiga.
- **No agrega ni cambia métricas.** Se usan las columnas que el driver ya publica.
- **No decide la adopción de nada.** Como máximo deja planteada una decisión con números.

---

## 8. Reproducción

```bash
for cell in actual no-floor-stops10 no-floor-stops15; do
  docker compose exec -T backend python manage.py config_algorithm_sweep \
    --csv "docs/experiments/balance-criterion-20260726-$cell.csv" \
    --only-cell "$cell" --seeds 1 2 3 --post-resequence &
done; wait
```

Un CSV y un flujo por celda, mismo grado de paralelismo para las tres.

---
---

# Resultados

**Datos:** `balance-criterion-20260726-{actual,no-floor-stops10,no-floor-stops15}.csv`.
**108 filas**: 3 celdas × 12 instancias × 3 semillas. Un CSV y un flujo por celda.
`post_resequence = True` en las 108 filas; `two_opt_gap = 0.0` en todas, es decir el post-pass
corrió y convergió. Nada se interrumpió y nada se re-corrió.

## 9. El instrumento

### 9.1 Comprobación de cordura — pasa

`actual` sobre `reference-n1607`, las 3 semillas:

| semilla | k | `drops` | `degenerate_routes` | `short_routes` | `dur_min_sec` | balance |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 25 | 0 | 0 | 0 | 8 938 | 0,830 |
| 2 | 25 | 0 | 0 | 0 | 9 083 | 0,845 |
| 3 | 25 | 0 | 0 | 0 | 9 089 | 0,844 |

k = 25, 0 drops, 0 degeneradas por duración, como estaba pre-registrado. **Hay algo que
interpretar.**

### 9.2 Las semillas son réplicas

`actual` da **0 de 12** instancias con réplicas idénticas: los tres travel de
`reference-n1607` son 58 552 / 60 688 / 57 465 y el balance de `area-27-n72` va de 0,748 a 0,910.
Las semillas llegan al solver, a diferencia del defecto 1.2.

`no-floor-stops10` tiene 2 de 12 instancias con réplicas idénticas en travel, balance y
`crossings_road`, y `no-floor-stops15` 3 de 12 (la tercera, `battery-n100`, sí varía en
`crossings_chord`: 3 / 4 / 3).
**Todas son instancias con k = 1 o k = 2** (`battery-n50`, `area-29-n43`, `battery-n100`): con una
o dos rutas, permutar el orden de los nodos casi no tiene desempates que cambiar y el post-pass
2-opt converge al mismo camino. Es degeneración estructural del caso, no del instrumento — y se
distingue del defecto 1.2 justamente porque ahí las idénticas aparecían en `reference-n1607` con
k = 25.

## 10. `reference-n1607` — el punto central del ciclo

### 10.1 Semilla por semilla

Δ travel contra la **misma semilla** de `actual`:

| celda | semilla | k | travel | Δ travel | balance | `dur_min_sec` | `degen.` | `short` | `road` | `chord` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `actual` | 1 | 25 | 58 552 | — | 0,830 | 8 938 | 0 | 0 | 31 | 37 |
| `actual` | 2 | 25 | 60 688 | — | 0,845 | 9 083 | 0 | 0 | 42 | 77 |
| `actual` | 3 | 25 | 57 465 | — | 0,844 | 9 089 | 0 | 0 | 30 | 44 |
| `no-floor-stops10` | 1 | 25 | 52 784 | −9,9 % | **0,011** | **120** | **1** | 1 | 49 | 39 |
| `no-floor-stops10` | 2 | 25 | 51 450 | −15,2 % | **0,011** | **120** | **1** | 1 | 47 | 45 |
| `no-floor-stops10` | 3 | 25 | 50 430 | −12,2 % | **0,011** | **120** | **1** | 1 | 21 | 35 |
| `no-floor-stops15` | 1 | 25 | 52 784 | −9,9 % | **0,011** | **120** | **1** | 1 | 49 | 39 |
| `no-floor-stops15` | 2 | 25 | 52 091 | −14,2 % | **0,011** | **120** | **1** | 1 | 47 | 46 |
| `no-floor-stops15` | 3 | 25 | 50 430 | −12,2 % | **0,011** | **120** | **1** | 1 | 21 | 35 |

**Las 3 de 3 semillas de los dos brazos sin piso de duración producen una ruta de 120 segundos.**
120 s es exactamente un tiempo de servicio con cero caminata: es una ruta de **un solo árbol**
(`short_routes = 1` lo confirma por la vía del conteo). Las otras 24 rutas quedan con duración
mediana ~10 300 s contra un T_max de 10 800 s.

### 10.2 Medias con desviación

| celda | k | travel | Δ travel | `crossings_road` | Δ road | `crossings_chord` | Δ chord | balance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `actual` | 25,0±0,0 | 58 902±1 339 | — | 34,3±5,4 | — | 52,7±17,4 | — | 0,840±0,007 |
| `no-floor-stops10` | 25,0±0,0 | 51 555±964 | **−12,5 % (real)** | 39,0±12,8 | **+13,6 % (empate)** | 39,7±4,1 | −24,7 % | **0,011±0,000** |
| `no-floor-stops15` | 25,0±0,0 | 51 768±988 | **−12,1 % (real)** | 39,0±12,8 | **+13,6 % (empate)** | 40,0±4,5 | −24,1 % | **0,011±0,000** |

## 11. Estado de la predicción principal

La predicción 4.1 tenía dos cláusulas. **La primera se cumple, y más fuerte de lo predicho. La
segunda no se puede evaluar, y hay que decirlo así.**

**Cláusula 1 — «falla el criterio operativo, al menos una semilla con `dur_min < 1 800`»:
CUMPLIDA.** No una semilla de tres: **las tres**. `dur_min_sec = 120` en las 3 semillas de
`stops10` y en las 3 de `stops15`.

**Cláusula 2 — «su ventaja en travel desaparece o se invierte en las semillas sin ruta
degenerada»: NO EVALUABLE.** No hay ninguna semilla sin ruta degenerada. El brazo produce el stub
en 3 de 3 corridas, así que el grupo de comparación que la predicción necesitaba está **vacío**.
La cláusula no se cumplió ni se falsó: quedó sin caso de prueba, y no se le puede acreditar nada.

Lo que sí se puede afirmar es más fuerte que la cláusula 2, y por eso el resultado no depende de
ella: bajo los defaults actuales **travel y ruta degenerada dejaron de estar confundidos y pasaron
a ser colineales**. En la medición vieja (defecto 1.1) el confundido era parcial —3 semillas con
stub, 2 sin— y se podía separar. Aquí la ventaja de −12,5 % en travel se mide **exclusivamente
sobre soluciones que contienen una ruta de un árbol**. No hay ninguna corrida de este brazo, bajo
los defaults de producción, en la que la ganancia de travel exista sin el stub. La ganancia no es
separable ni mensurable por separado.

**Predicción 4.2 — CUMPLIDA.** `no-floor-stops15` muestra el mismo patrón: stub en 3 de 3
semillas, mismo `dur_min = 120`, mismo balance 0,011. El problema no es la altura del piso de
paradas: **es la familia sin piso de duración.**

### 11.1 El piso de paradas es en gran medida inerte, y se compra

**20 de las 36 filas de `stops10` y `stops15` son idénticas entre sí** —mismo travel, mismo
balance, mismos `crossings_road`—, incluidas las semillas 1 y 3 de `reference-n1607`. Subir el
piso de 10 a 15 paradas no cambia la solución encontrada.

El mecanismo es visible en la aritmética del objetivo. La ruta stub tiene 1 parada, así que viola
los dos pisos: el déficit se paga a 10 000 por parada faltante, o sea 90 000 con `stops10` y
140 000 con `stops15`. **Que las soluciones sean idénticas significa que 50 000 adicionales de
penalidad no alcanzan para mover el óptimo encontrado.** El piso de paradas no prohíbe el stub:
le pone precio, y el solver lo paga.

Y no lo paga porque absorber el árbol sea infactible. Con `travel = 51 555` y 1 607 árboles a
120 s, la suma de duraciones es 244 395 s; las 24 rutas de trabajo ocupan 244 275 s contra una
capacidad de 24 × 10 800 = 259 200 s, es decir **~14 925 s de holgura agregada** y rutas al 94,2 %
de T_max en promedio. Hay lugar donde poner el árbol. Con estos datos **no se puede distinguir**
si el movimiento cuesta más que la penalidad o si GLS no lo encuentra en los 120 s de límite; lo
que sí queda medido es que la infactibilidad dura no es la explicación.

## 12. Áreas — relleno y auto-cruces

`relleno_msf_sec`, media ± sd, Δ vs `actual` (umbral pre-registrado −30 %):

| celda | `area-26-n157` | `area-27-n72` | `area-29-n43` |
| --- | ---: | ---: | ---: |
| `actual` (base) | 1 233±278 | 1 580±212 | 229±15 |
| `no-floor-stops10` | 720±13 → **−41,6 %** ✅ | 143±15 → **−91,0 %** ✅ | 167±0 → **−27,2 %** ❌ |
| `no-floor-stops15` | 652±46 → **−47,1 %** ✅ | 147±19 → **−90,7 %** ✅ | 167±0 → **−27,2 %** ❌ |

Las seis diferencias son **reales** bajo la regla de varianza. `area-26-n157` —la instancia que
bloqueó la serie tres ciclos— vuelve a pasar con holgura, coherente con el re-juicio de
`sweep-metrology-20260720.md`. **La que falla ahora es `area-29-n43`, por 2,8 puntos.**

**Sensibilidad declarada:** `area-29` mide −27,2 % con desviación 0, así que el ítem 4 pasaría con
cualquier umbral hasta −27 % y falla desde −28 %. Un lector que prefiera −25 % obtiene ✅ en ese
ítem. **No cambia el veredicto del ciclo**, porque los ítems 1 y 8 fallan igual.

`crossings_road` en áreas **no empeora en ninguna**: `area-26` 4,7±0,5 → 3,7±0,5 (real) y
4,0±0,8; `area-27` 4,0±0,8 → 2,0±1,4 (empate); `area-29` 1,3±0,5 → 1,0±0,0 (empate). Ítem 5 ✅.

## 13. Suite completa — balance, drops y degeneración

| celda | `drops` | balance mín. (media) | instancias <0,60 en media | balance peor semilla | instancias <0,60 en alguna semilla | rutas degeneradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `actual` | **0** | **0,828** (`area-27-n72`) | **0** | **0,748** | **0** | **0** |
| `no-floor-stops10` | **0** | 0,011 (`reference-n1607`) | 1 | 0,011 | 4 | **3** |
| `no-floor-stops15` | **0** | 0,011 (`reference-n1607`) | 2 | 0,011 | 2 | **3** |

Balance medio por instancia:

| instancia | `actual` | `no-floor-stops10` | `no-floor-stops15` |
| --- | ---: | ---: | ---: |
| `area-29-n43` | 1,000±0,00 | 1,000±0,00 | 1,000±0,00 |
| `battery-n50` | 0,958±0,03 | 1,000±0,00 | 1,000±0,00 |
| `area-27-n72` | 0,828±0,07 | 1,000±0,00 | 1,000±0,00 |
| `battery-n100` | 0,934±0,07 | 0,607±0,06 | 0,651±0,00 |
| `area-26-n157` | 0,855±0,05 | 0,838±0,01 | 0,797±0,02 |
| `battery-n200` | 0,906±0,01 | 0,624±0,16 | **0,543±0,08** |
| `battery-sparse-n250` | 0,834±0,02 | 0,666±0,02 | 0,666±0,02 |
| `battery-n400` | 0,931±0,05 | 0,860±0,02 | 0,831±0,01 |
| `battery-sparse-n500` | 0,905±0,05 | 0,858±0,02 | 0,889±0,02 |
| `battery-n800` | 0,844±0,01 | 0,735±0,04 | 0,735±0,04 |
| `battery-n1000` | 0,847±0,01 | 0,639±0,20 | 0,717±0,12 |
| `reference-n1607` | 0,840±0,01 | **0,011±0,00** | **0,011±0,00** |

Las tres rutas degeneradas de cada brazo son las de `reference-n1607`; **ninguna otra instancia
produce una ruta bajo 1 800 s en ninguna celda**.

## 14. Las dos lecturas del criterio

Es el objeto del ciclo, así que se reportan las dos, completas.

| # | Criterio | `actual` | `no-floor-stops10` | `no-floor-stops15` |
| --- | --- | :---: | :---: | :---: |
| 1 | n=1607 `crossings_road` −≥30 % | base | ❌ +13,6 % | ❌ +13,6 % |
| 2 | n=1607 travel ≤+3 % | base | ✅ −12,5 % | ✅ −12,1 % |
| 3 | n=1607 k ≤26 | ✅ 25 | ✅ 25 | ✅ 25 |
| 4 | Áreas `relleno_msf` −≥30 % | base | ❌ `area-29` −27,2 % | ❌ `area-29` −27,2 % |
| 5 | Áreas `crossings_road` sin empeorar | base | ✅ | ✅ |
| 6 | `drops` = 0 | ✅ | ✅ | ✅ |
| 7 | **Reparto:** balance ≥0,60 | ✅ | ❌ 0,011 | ❌ 0,011 |
| 8 | **Operativo:** 0 degeneradas por duración | ✅ | ❌ 3/3 semillas | ❌ 3/3 semillas |

**Lectura CON el ítem de balance:** `stops10` y `stops15` fallan los ítems **1, 4, 7 y 8**.
**Lectura SIN el ítem de balance:** fallan los ítems **1, 4 y 8**.

**El desdoblamiento del criterio no cambia el veredicto de ningún brazo.** Quitar el ítem 7
elimina un fallo de cuatro y deja tres en pie, uno de ellos el criterio operativo que el propio
desdoblamiento declara irrenunciable.

---

## 15. Veredicto

**Ninguna celda queda verificada contra el criterio a priori, en ninguna de las dos lecturas. No
se cambia ningún default de producción.**

| Celda | Veredicto |
| --- | --- |
| `actual` | **Control válido.** Reproduce k=25, 0 drops y 0 degeneradas en las 3 semillas; balance mínimo 0,828 en la suite. La comprobación de cordura pasa, así que el resto del ciclo es interpretable. |
| `no-floor-stops10` | **No verificada — falla el criterio operativo, no el de reparto.** Baja el travel de n=1607 un −12,5 % (real) y el relleno de dos de las tres áreas, pero produce una ruta de un solo árbol en **3 de 3 semillas**, empeora `crossings_road` (+13,6 %, empate, contra un exigido −30 %) y se queda a 2,8 puntos del relleno de `area-29`. |
| `no-floor-stops15` | **No verificada — idéntico modo de fallo.** Subir el piso de 10 a 15 paradas no cambia la solución en 20 de 36 filas. Además es el único brazo con dos instancias bajo 0,60 en media (`battery-n200` 0,543). |

### La premisa que abrió el ciclo queda refutada

`no-floor-stops10` **no era «el mejor brazo en travel que muere sólo por balance».** Medido bajo
los defaults actuales, con réplicas reales y su propia línea base:

1. **No muere sólo por balance.** Falla además el criterio operativo (ítem 8), los auto-cruces
   sobre calle (ítem 1) y el relleno de `area-29` (ítem 4). El desdoblamiento del criterio de
   balance, que era la vía por la que este brazo podía revivir, **no lo rescata**: le quita un
   fallo de cuatro.
2. **Su ventaja en travel no es separable de la ruta degenerada.** En la medición vieja el
   confundido era parcial y las semillas sin stub llegaban a +5,5 %; aquí el stub aparece en 3 de
   3, así que el −12,5 % se mide íntegramente sobre soluciones con un árbol sin jornada. No queda
   ninguna corrida en la que la ganancia exista sin el defecto.
3. **El retrato favorable del brazo era una sola muestra afortunada.** Las cifras que lo
   presentaban con `dur_min = 7 835 s` y balance 0,727 venían de la corrida con semillas falsas
   (defecto 1.2), sin post-pass y sin barras de error.

### Qué queda descartado, y por qué

- **La familia sin piso de duración, cerrada también por la lectura operativa.** Con piso de
  paradas de 10 o de 15, bajo los defaults actuales, el stub aparece en **6 de 6** corridas de
  `reference-n1607`. Ya estaba cerrada por relleno y por varianza
  (`sweep-metrology-20260720.md`); ahora lo está por la única lectura que el desdoblamiento
  declaraba no negociable. **No se reabre sin un mecanismo nuevo**, y subir el piso de paradas no
  es uno: es el eje que este ciclo midió y encontró inerte.
- **El piso de paradas como prohibición.** Queda medido que **es un precio, no una restricción**:
  50 000 adicionales de penalidad no mueven la solución en 20 de 36 filas, y la ruta de un árbol
  sobrevive pagando. Cualquier propuesta futura que quiera prohibir stubs necesita una cota dura,
  no una penalidad — y con ~14 925 s de holgura agregada disponible, el problema no es la
  factibilidad.
- **El desdoblamiento del criterio, como palanca de rescate.** Se pre-registró para ver si algún
  brazo sobrevivía la lectura operativa, y la respuesta medida es que el brazo candidato falla
  precisamente esa lectura. El desdoblamiento **se sostiene como aclaración conceptual** —«las
  rutas duran parecido» y «cada ruta es una jornada entregable» son criterios distintos, y la
  decisión de producto de 2026-07-19 sigue siendo la razón para separarlos— pero **no cambia
  ningún veredicto de la serie**, y no se puede invocar en el futuro para revivir un brazo que
  falle el ítem 8.

### Lo que este ciclo deja como limitación, sin haberlo medido

El único ítem que quedó *cerca* es el relleno de `area-29-n43`: −27,2 % contra −30 %, con
desviación 0. Es un fallo real bajo el umbral pre-registrado y así se reporta, pero es un fallo
distinto en naturaleza de los otros dos, que no son marginales. Y `crossings_road` empeorando
+13,6 % con desviación ±12,8 —un empate bajo la regla de varianza— dice que con 3 semillas **este
ciclo no tiene potencia para resolver el signo del efecto sobre los auto-cruces de calle**. Lo que
sí resuelve, y sin ambigüedad, es el ítem 8: `dur_min = 120` en 6 de 6 corridas no es una cuestión
de potencia estadística.

Ninguna de estas dos observaciones se convierte en propuesta aquí, y no hay evidencia para
afirmar nada sobre ellas más allá de lo escrito.
