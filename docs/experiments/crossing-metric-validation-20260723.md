# Validación de la métrica de auto-cruces contra la geometría real de calles

**Fecha:** 2026-07-23
**Estado al commitear esta sección:** pre-registro. Motivación, diseño, celdas, instancias,
métricas, predicciones y criterio se commitean **antes** de medir nada. Los resultados se
agregan después, sin tocar el criterio.

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual, coeficiente
de span espacial 3) intactos. Lo nuevo es opt-in.

---

## 1. Motivación

La métrica de calidad geométrica de toda la serie es `self_crossings`
(`backend/apps/optimization/route_audit.py`): pares de segmentos **no adyacentes** de la misma
ruta que se cruzan estrictamente. Se calcula sobre las **cuerdas rectas** que unen paradas
consecutivas, proyectadas con `project_equirectangular`.

Al revisar las capas del sistema aparece que esa geometría no corresponde a ninguna otra:

| capa | geometría que usa |
| --- | --- |
| objetivo del solver | tiempo de red OSRM (`time_callback`) |
| post-pass 2-opt | matriz de tiempo OSRM |
| mapa que ve el censista | polilínea real de calles (`osrm.fetch_route_path`) |
| **métrica `self_crossings`** | **cuerdas rectas entre paradas** |

Ni el solver optimiza esas cuerdas ni el censista las ve. La métrica es un **proxy sin
referente verificado**: puede ser un buen proxy, pero nunca se comprobó.

El síntoma que motiva la comprobación es una contradicción con un teorema. El 2-opt de camino
abierto sobre una métrica que cumple desigualdad triangular en el plano **elimina** los
auto-cruces (todo cruce admite un intercambio 2-opt que acorta). En las mediciones publicadas el
post-pass los **multiplica por ocho** en 12 de 12 instancias
(`docs/experiments/no-floor-balance-sweep-20260719.md`, brazo 5: 6,3 → 51,0 en `n=1607`). Una de
dos: o el 2-opt genera zigzag real sobre la red, o la métrica de cuerdas no mide lo que el 2-opt
optimiza. **Hoy no se puede distinguir, y de esa distinción depende un veredicto ya publicado.**

## 2. Preguntas

1. ¿La métrica de cuerdas ordena las soluciones igual que la métrica sobre la geometría real?
2. ¿El efecto "el post-pass 2-opt empeora los auto-cruces" sobrevive al cambio de geometría?
3. ¿Cuánto tiempo de viaje pierde la configuración de producción por secuencias no 2-óptimas?

## 3. Diseño

**Celdas (6).** Solo aquellas donde la distinción cuerda/red puede voltear un veredicto: las
tres bases cuya secuencia el post-pass modifica, y sus tres post-pass.

```
actual                      actual+reseq
no-floor                    no-floor+reseq
upper-tmax-tmin9000         upper-tmax-tmin9000+reseq
```

**Instancias.** Las 12 congeladas de `docs/experiments/instances/`.

**Semillas.** 3 réplicas reales (permutación del orden de nodos; OR-Tools no expone RNG,
verificado). Todas las mediciones `+reseq` de reportes anteriores tienen σ = 0,0 entre sus tres
semillas: son tres copias del mismo número, porque el driver escribía la semilla en el CSV pero
no la pasaba al solver. **Este ciclo re-corre sus propias líneas base**; no se compara contra
cifras publicadas por otros reportes (la varianza entre corridas supera la varianza entre
semillas de una misma corrida).

**Métricas nuevas, junto a las existentes.**

| columna | definición | costo |
| --- | --- | --- |
| `crossings_chord` | `self_crossings` sobre las cuerdas rectas entre paradas — la actual, control | 0 |
| `crossings_road` | `self_crossings` sobre la polilínea de `osrm.fetch_route_path` | alto |
| `two_opt_gap` | `(travel − travel tras 2-opt) / travel`, por solución, matriz OSRM | 0 |

`two_opt_gap` es la definición **métrica-consistente** de "ruta ilógica": mide el tiempo caminado
que le sobra a la secuencia, en la misma métrica que el solver optimiza y que el censista camina.
No usa geometría y no puede tener el desajuste que motiva este ciclo.

## 4. Predicciones registradas ANTES de medir

- **P1.** `crossings_chord` ≥ `crossings_road` en la mayoría de celdas: las cuerdas ignoran que la
  caminata sigue calles, y dos paradas contiguas por calle pueden tener cuerdas que se cruzan sin
  que los caminos reales lo hagan.
- **P2.** El efecto del post-pass será **marcadamente menor** sobre `crossings_road` que sobre
  `crossings_chord`. Si `crossings_road` no sube, el veredicto del post-pass cae.
- **P3.** `two_opt_gap` de `actual` será estrictamente positivo y del orden de **5 %** (estimado
  de las cifras publicadas: 62 005 → 58 818). Es la respuesta directa a "cuánto pierde producción
  por secuencias ilógicas".
- **P4.** `two_opt_gap` ≈ 0 en los brazos `+reseq`, por construcción (el 2-opt convergió). Es la
  comprobación de cordura del instrumento: si NO da ~0, la implementación está mal y no hay nada
  que interpretar.

## 5. Criterio a priori

Sobre las 6 celdas × 12 instancias × 3 semillas, correlación de rangos de Spearman entre
`crossings_chord` y `crossings_road`:

| ρ | lectura | consecuencia |
| --- | --- | --- |
| **ρ ≥ 0,80** | la métrica de cuerdas es un proxy válido | la serie queda validada; el veredicto del post-pass se mantiene y queda mejor fundado que hoy |
| **0,50 ≤ ρ < 0,80** | proxy parcial | se reportan ambas columnas en adelante; ningún veredicto se revierte sin re-medir |
| **ρ < 0,50** | la métrica no tiene referente | el eje de calidad geométrica de la serie se re-lee en un ciclo posterior con su propio pre-registro |

**Prueba decisiva, independiente de ρ:** el signo del efecto del post-pass sobre `crossings_road`.
Si sube → el 2-opt sí genera zigzag real y el veredicto queda reforzado. Si baja o empata → el
veredicto descansaba en un artefacto de dibujo.

**Las tres salidas son publicables.** Este ciclo no busca una ganadora: busca saber si la regla
con la que se juzgaron diez ciclos mide algo. Un "la métrica era válida" es un resultado tan
citable como lo contrario.

## 6. Lo que NO hace este ciclo

- No cambia ningún default de producción. Ni siquiera propone uno.
- No cambia el criterio de aceptación de la serie. Si la métrica resulta sin referente, el
  criterio se re-lee en un ciclo posterior y con su propio pre-registro.
- No corre el 2-opt sobre matriz haversine: haría converger justamente la métrica bajo sospecha.

## 7. Entregable de método

El barrido **persiste la secuencia de paradas por ruta** en un JSON paralelo al CSV. Los
auto-cruces dependen de la secuencia, que el barrido no guardaba (hace rollback de su
transacción). Guardarla convierte toda corrección futura de métrica de secuencia en un re-juicio
barato, sin re-resolver.

## 8. Costos y riesgos

- **CPU.** Exige re-resolver: 6 celdas × 12 instancias × 3 semillas con `SOLVER_TIME_LIMIT_SEC`
  de producción.
- **`crossings_road` es O(m²).** La polilínea trae decenas de vértices por tramo → miles de
  segmentos por ruta. Reutiliza el motor `self_crossings` ya vectorizado (prefiltro de cajas
  contenedoras), y se verifica su equivalencia sobre casos chicos ANTES de medir.
- **Llamadas OSRM.** `fetch_route_path` por ruta, ya paralelizado, acotado a 8 en vuelo para no
  inundar el contenedor OSRM.

---

## Resultados

Datos: `crossing-metric-validation-20260723-{actual,no-floor,upper-tmax-tmin9000,actual_reseq,
no-floor_reseq,upper-tmax-tmin9000_reseq}.csv` y sus `.sequences.jsonl`. **216 filas**: 6 celdas
× 12 instancias × 3 semillas. Un CSV y un flujo por celda, mismo grado de paralelismo para los
seis. `wall_clock` no se usa para juzgar nada.

### Comprobaciones del instrumento (antes de leer nada más)

- **P4 (cordura) — pasa.** `two_opt_gap` = 0,0000 exacto en **las 36 filas** de cada uno de los
  tres brazos `+reseq`. El 2-opt convergió; el instrumento mide lo que dice medir.
- **Semillas reales — pasa.** Solo 6 de 72 grupos `(celda, instancia)` tienen σ = 0 entre sus
  tres semillas, y son casos `k = 1` deterministas por construcción (p. ej. `no-floor` en
  `battery-n50`). La σ de travel entre semillas tiene mediana 181 s y llega a 3 703 s: las
  permutaciones de nodos llegaron al solver.

### Pregunta 1 — ¿ordena igual la métrica de cuerdas que la de red?

Correlación de rangos de Spearman entre `crossings_chord` y `crossings_road`:

| conjunto | filas | ρ |
| --- | ---: | ---: |
| **todas** | 216 | **0,527** |
| solo bases (sin `+reseq`) | 108 | 0,558 |
| solo `+reseq` (2-óptimas) | 108 | 0,871 |
| **solo `reference-n1607`** | 18 | **−0,575** |

El ρ global de **0,527** cae en la banda **0,50 ≤ ρ < 0,80: proxy parcial**. Pero ese número
pooled esconde una heterogeneidad fuerte: entre soluciones ya 2-óptimas las dos métricas
concuerdan casi perfectamente (0,871), mientras que **sobre la instancia insignia `n=1607` la
correlación es negativa (−0,575): la métrica de cuerdas invierte el orden real.**

### Pregunta 2 — ¿sobrevive al cambio de geometría el efecto del post-pass? (prueba decisiva)

Efecto del post-pass 2-opt, pares base → `+reseq`, sobre 36 filas emparejadas por celda:

| par | `crossings_chord` total | `crossings_road` total | dirección road (up/down/eq de 36) |
| --- | --- | --- | --- |
| `actual` → `+reseq` | 608 → 621 (**+2 %**) | 610 → 463 (**−24 %**) | 1 / 30 / 5 |
| `no-floor` → `+reseq` | 114 → 608 (**×5,3**) | 844 → 464 (**−45 %**) | 2 / 29 / 5 |
| `upper-tmax-tmin9000` → `+reseq` | 227 → 651 (**×2,9**) | 948 → 543 (**−43 %**) | 1 / 31 / 4 |

Sobre las **mismas soluciones**, la métrica de cuerdas dice que el post-pass **multiplica** los
auto-cruces (hasta ×5,3) y la métrica de red dice que los **reduce** entre un 24 % y un 45 %. El
signo del efecto sobre `crossings_road` es **negativo o nulo en las 36 instancias de cada par;
nunca sube.** Por instancia, el 2-opt sube `crossings_road` en 4 de las 108 filas emparejadas y
lo baja o empata en las otras 104.

Esto activa la lectura pre-registrada del §5: *"Si baja o empata → el veredicto descansaba en un
artefacto de dibujo."* El 2-opt minimiza travel de red, y al hacerlo **limpia** la geometría de
calles; la métrica de cuerdas lo reporta como un empeoramiento porque las cuerdas rectas entre
las paradas re-secuenciadas fabrican cruces que las calles realmente caminadas no tienen.

### Pregunta 3 — ¿cuánto pierde producción por secuencias no 2-óptimas?

`two_opt_gap` de `actual`, la fracción de travel de red que un 2-opt de camino abierto elimina:

| instancia | `two_opt_gap` (actual) |
| --- | ---: |
| `reference-n1607` | **0,019** (1,9 %) |
| áreas chicas (27 / 29) | 0,60 / 0,49 |
| batería densa (800 / 1000) | 0,01 / 0,03 |

En `n=1607`, producción pierde **1,9 %** de travel por secuencias no 2-óptimas — positivo, como
predijo P3, pero **por debajo del ~5 % estimado**. La pérdida es grande solo en áreas chicas y
holgadas, donde el piso `T_min` fuerza relleno que el 2-opt puede recortar.

### Cuadro de predicciones

| # | predicción | resultado | veredicto |
| --- | --- | --- | --- |
| P1 | `crossings_chord` ≥ `crossings_road` en la mayoría de celdas | se cumple en `actual` pero **se invierte en la familia `no-floor`/`upper`**: en `n=1607` chord 16/22 vs road 73/71 | **parcial / refutada donde importa** |
| P2 | el post-pass sube mucho menos `crossings_road` que `crossings_chord` | más fuerte que lo predicho: **road baja**, no sube | **acertada (dirección más extrema)** |
| P3 | `two_opt_gap` de `actual` ≈ 5 % | 1,9 % en `n=1607` (positivo, menor) | **dirección acertada, magnitud sobre-estimada** |
| P4 | `two_opt_gap` ≈ 0 en `+reseq` (cordura) | 0,0000 exacto en 108/108 filas | **acertada** |

### El hallazgo colateral: la métrica invierte el orden geométrico de la familia sin piso

En `n=1607`, la métrica de cuerdas rankea a `no-floor` como la geometría **más limpia**
(chord 16,0 ± 11,8) y a `actual` como una de las más sucias (chord 65,3 ± 7,0). La métrica de red
dice **exactamente lo contrario**: `actual` road **43,0 ± 4,0** contra `no-floor` road
**73,0 ± 12,0**. Sobre las calles reales `actual` es casi el doble de limpia que `no-floor`. La
supuesta ventaja geométrica de la familia sin piso —una de las cifras destacadas de
`no-floor-balance-sweep-20260719.md`— es en `n=1607` un artefacto de las cuerdas: quitar el piso
produce rutas cuyas paradas contiguas en línea recta casi no se cruzan, pero cuyos caminos de
calle se enroscan más que los de producción.

---

## Veredicto

**La métrica de auto-cruces sobre cuerdas rectas es un proxy PARCIAL de la geometría real
(ρ = 0,527, banda 0,50–0,80), y en el régimen que más se ha usado para juzgar —la instancia densa
`n=1607`— no solo es débil sino que INVIERTE el orden (ρ = −0,575).**

Se aplica el criterio a priori **sin renegociarlo**:

- ρ global 0,527 → **proxy parcial**. Consecuencia pre-registrada: *"se reportan ambas columnas
  en adelante; ningún veredicto se revierte sin re-medir."*
- **Prueba decisiva (independiente de ρ):** el signo del efecto del post-pass sobre
  `crossings_road` es **negativo o nulo en 104 de 108 filas, nunca positivo de forma real.** El
  veredicto publicado "el post-pass 2-opt empeora los auto-cruces ×8" **descansaba en un artefacto
  de dibujo**: el 2-opt reduce los cruces sobre las calles que el censista camina. Este ciclo
  re-midió el post-pass explícitamente, así que la regla "no revertir sin re-medir" se satisface.

**No se cambia ningún default de producción.** El post-pass es opt-in y sigue siéndolo; no había
default que cambiar. La re-lectura del criterio de calidad de la serie —si se adopta
`crossings_road` como métrica de referencia— se hace en un **ciclo posterior con su propio
pre-registro**, como fija el §6; este ciclo no la ejecuta.

### Lo que queda establecido

1. **El instrumento es válido** (P4: gap 0 exacto en todas las `+reseq`). El desacuerdo
   chord/road no es ruido de medición: es sistemático y con signo.
2. **La métrica de cuerdas concuerda con la de red solo cuando la solución ya es 2-óptima**
   (ρ = 0,871 en `+reseq`) **y falla sobre soluciones crudas** (ρ = 0,558 en bases, −0,575 en
   `n=1607`). Es un proxy del resultado de un 2-opt, no de la geometría caminada.
3. **El post-pass 2-opt NO ensucia la geometría real; la limpia** (road −24 % a −45 %). El "×8"
   publicado es la firma de que las cuerdas entre paradas re-secuenciadas fabrican cruces
   inexistentes en la calle. Queda **descartado** usar el aumento de `crossings_chord` como
   evidencia contra el post-pass.
4. **La ventaja geométrica de la familia sin piso en `n=1607` es un artefacto de cuerdas**
   (`actual` road 43 < `no-floor` road 73). No reabre `no-floor` —que ya estaba descartado por
   degeneración y balance, no por geometría— pero retira uno de sus argumentos a favor.

### Lo que este ciclo deja abierto, con dato nuevo para el siguiente

Adoptar `crossings_road` como criterio de calidad geométrica de la serie es ahora una **propuesta
verificada**: la columna existe, es reproducible y ordena las soluciones de forma consistente con
lo que el solver optimiza y el censista camina. Su adopción —y la re-lectura de los veredictos que
se juzgaron con cuerdas— corresponde a un ciclo con su propio pre-registro. Las secuencias de
parada quedan persistidas (`.sequences.jsonl`), así que ese re-juicio no exige re-resolver.

---

## Reproducción

```bash
# Infra compartida (db + osrm) y suite congelada
make shared-up
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py load_instances

# Un flujo por celda, en paralelo, un CSV por celda (+ .sequences.jsonl al lado)
BASE=docs/experiments/crossing-metric-validation-20260723
for cell in actual no-floor upper-tmax-tmin9000 \
            actual+reseq no-floor+reseq upper-tmax-tmin9000+reseq; do
  safe=$(echo "$cell" | tr '+' '_')
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv "${BASE}-${safe}.csv" --only-cell "$cell" --seeds 1 2 3 &
done
wait
```

El ρ de Spearman es el rango-Pearson de `crossings_chord` contra `crossings_road` sobre las 216
filas; la prueba decisiva es el signo de `crossings_road[+reseq] − crossings_road[base]` emparejado
por `(instancia, semilla)`. Ambos son aritmética sobre los CSV, sin solver.
