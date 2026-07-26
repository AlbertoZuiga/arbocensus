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
