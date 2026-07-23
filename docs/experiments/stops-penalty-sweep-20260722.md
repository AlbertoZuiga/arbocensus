# Barrido de fuerza del piso de paradas sobre `feasible-floor-b095`

**Fecha:** 2026-07-22
**Estado al commitear esta sección:** pre-registro. Diseño, criterio, umbrales y la
aritmética de la Fase 0 se commitean **antes** de medir nada. Los resultados se agregan
después, sin tocar el criterio.

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual,
coeficiente de span espacial 3) intactos. Lo nuevo es opt-in.

---

## Por qué este ciclo

`sweep-metrology-20260720.md` dejó a `feasible-floor-b095` pasando **siete de ocho**
criterios y fallando uno: **rutas degeneradas**. El fallo es de cola, no de media.

`multistart-sweep-20260721.md` cerró la explicación alternativa. El multi-arranque —
resolver con varias semillas y quedarse con la mejor — **no mata la cola**: los cuatro
brazos empatan con N=1 bajo la regla de varianza, y con presupuesto total fijo además
rompe travel (+5.8 %). La degeneración de `b095` **no es ruido de búsqueda**: es una
solución que el modelo considera buena. Si el modelo la considera buena, hay que
atacarla desde el **modelo**.

### Qué marca exactamente la degeneración

Medido con réplicas reales sobre `b095` (`multistart-sweep-20260721-feasible-floor-b095-n1.csv`,
5 semillas):

| Semilla | k | `dur_min_sec` | `degenerate_routes` | balance |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 25 | 7 159 | 1 | 0.666 |
| 2 | 25 | 8 592 | 0 | 0.798 |
| 3 | 25 | 7 736 | 1 | 0.718 |
| 4 | 25 | 8 186 | 1 | 0.761 |
| 5 | 25 | 8 775 | 0 | 0.818 |

**3 de 5 réplicas degeneran; 0.6 ± 0.5 rutas por réplica.** Las filas degeneradas están
**todas** en `reference-n1607`, y **todas** tienen `dur_min` muy por encima del umbral de
1 800 s. La marca no viene de la duración: viene del **conteo de paradas**. Son rutas de
casi dos horas con **menos de 5 árboles censados** — casi puro desplazamiento, casi nada
de censo.

### El hueco concreto

La familia de piso de paradas ya existe y ya se barrió (`stops-floor-sweep-20260720.md`,
`combined-floor-sweep-20260720.md`): `no-floor-stops{5,10,15}`, y combinados
`b060+stops10`, `b070+stops10`, `b085+stops10`. **No existe `b095+stops10`**, que es
justo la combinación que ataca el único fallo vivo del mejor candidato de la serie. Ese
es el punto de partida de este ciclo — no "agregar penalización de paradas" desde cero.

---

## Fase 0 — aritmética de la fuerza de la penalización (antes de medir)

La serie barrió el **umbral** de paradas (5/10/15) y **nunca la fuerza**. Antes de
diseñar la grilla hay que responder si `STOPS_FLOOR_PENALTY = 10 000` es lo bastante
grande frente al costo de los movimientos que arreglarían la degeneración. Si resultara
blanda, eso explicaría por sí solo por qué los `stops-floor` previos no cerraron el fallo.

### Cómo entra la penalización en el objetivo

`STOPS_FLOOR_PENALTY` se cobra **por parada faltante** sobre el cumul final de la
dimensión `Stops` (`solver.py`, `SetCumulVarSoftLowerBound`). Compite contra dos términos:

- el **evaluador de arco**, en segundos (`travel + servicio`), y
- el **span espacial**, `spatial_span_coef = 3` sobre la dimensión `Distance` en **metros**.

Medido sobre las instancias congeladas (aritmética pura, sin solver):

| Instancia | n | `nn` travel (s) | `nn` geo (m) | arco medio (s) |
| --- | ---: | ---: | ---: | ---: |
| `reference-n1607` | 1 607 | 17.1 | 19.9 | 1 117.6 |
| `area-26-n157` | 157 | 15.5 | 17.1 | 527.5 |

Costo objetivo de absorber **una parada vecina** en `reference-n1607`:

```text
17.1 s (arco)  +  3 × 19.9 m (span)  =  76.7 unidades de objetivo
```

Contra una penalización de **10 000 por parada faltante**.

### Veredicto aritmético, anterior al resultado

**La penalización NO es blanda para los movimientos que arreglarían la degeneración.**
Es **≈130×** el costo de absorber una parada geométricamente adyacente. Sólo se vuelve
pagable para movimientos geométricamente absurdos: el punto de indiferencia está en un
desvío de `10 000 / 3 ≈ 3 300 m` por parada, dos órdenes de magnitud sobre el espaciado
típico entre árboles (≈20 m).

Y en la escala de la ruta degenerada: bajo `stops10`, una ruta de 4 paradas tiene un
déficit de 6 y paga **60 000**, contra un `FIXED_VEHICLE_COST` de **100 000**.

**Consecuencia para el diseño, fijada aquí:** la hipótesis "los stops-floor previos no
cerraron el fallo porque la penalización era blanda" queda **descartada por aritmética,
antes de medir**. El barrido de fuerza se corre igual, pero con una predicción
pre-registrada distinta: si `b095+stops10` no cierra la degeneración, **subir la fuerza
tampoco lo hará**, y el fallo será estructural (no hay dónde poner los árboles) en vez de
tarifario. Un barrido de fuerza que muestre una meseta es evidencia a favor de eso.

### Verificación del mecanismo en un caso mínimo

El régimen existe y es observable (test `test_stops_floor_is_a_price_the_solver_pays_until_it_is_dear_enough`).
12 nodos uniformes bajo presión de span global, piso de 5 paradas:

| Penalización | rutas | objetivo | déficit |
| ---: | --- | ---: | ---: |
| — (`no-floor`) | 3,3,3,3 | 914 080 | — |
| 1 000 | 3,3,3,3 | 922 080 | 8 (paga) |
| 10 000 | 3,3,3,3 | 994 080 | 8 (paga) |
| 100 000 | 6,6 | 1 254 200 | **0 (reestructura)** |

El solver **paga** el piso mientras sea más barato que reestructurar, y **lo cumple**
cuando el precio supera al span. La brecha de objetivo es exactamente `déficit × penalización`,
lo que confirma que los vehículos vacíos no pagan.

### Por qué la degeneración puede ser estructural

En `reference-n1607` el servicio total es `1 607 × 120 = 192 840 s`; con `T_max = 10 800 s`
el mínimo por servicio es `k ≥ 18`, y con travel el solver fija **k = 25.0 ± 0.0 en todos
los brazos y todas las semillas**. La mediana de duración de `b095` está en ~10 450 s
contra un `T_max` de 10 800: las otras 24 rutas están **saturadas**. La holgura total para
absorber los ~4 árboles de la ruta degenerada es de unos 8 400 s, contra un costo de
`4 × 120 = 480 s` de servicio más los desvíos. **Es factible, pero por poco** — lo que
encaja con que ocurra en 3 de 5 semillas y no en 5 de 5.

El control `actual` demuestra que la carga **sí** se puede repartir a k=25: llega a
`dur_min ≈ 9 000`, balance 0.84 y **0 degeneradas**. La hipótesis es viable, no está
muerta de entrada.

---

## Hipótesis a falsar

> Un piso de paradas suficientemente fuerte sobre `b095` elimina las rutas degeneradas en
> **todas** las réplicas sin degradar la media (travel, cruces, relleno de áreas) más allá
> de la regla de varianza.

Si pasa el criterio **completo**, es la primera ganadora verificada de la serie, y se dirá
con esas palabras. Si no, no.

---

## Diseño

Estrategia `spatial_term`, **12 instancias congeladas**, **5 réplicas reales** (semillas
1–5, permutación de nodos), driver `config_algorithm_sweep` con overrides de CLI. Un CSV
y un flujo por brazo.

| # | Brazo | Celda / override | Papel |
| --- | --- | --- | --- |
| 1 | `actual` | — | Control (producción). Re-corrido en este ciclo. |
| 2 | `feasible-floor-b095` | — | Candidato de la serie. Re-corrido: es la línea base del fallo. |
| 3 | `feasible-floor-b095-stops5` | umbral 5 | Umbral igual al de la definición de degeneración. |
| 4 | **`feasible-floor-b095-stops10`** | umbral 10 | **La celda que falta.** |
| 5 | `feasible-floor-b095-stops15` | umbral 15 | Umbral alto. |
| 6 | `feasible-floor-b095-stops10` | `--stops-penalty 1000` | Fuerza baja (≈13× el costo de una parada vecina). |
| 7 | `feasible-floor-b095-stops10` | `--stops-penalty 100000` | Fuerza alta (= `FIXED_VEHICLE_COST`: una parada faltante cuesta un vehículo entero). |

**Dos ejes, un centro común.** Brazos 3–4–5 barren el **umbral** con la fuerza por
defecto; brazos 6–4–7 barren la **fuerza** con el umbral 10. `b095+stops10` a 10 000 es la
celda compartida por ambos ejes.

`actual` y `b095` se **re-corren** en vez de releerse del ciclo anterior: los siete brazos
deben correr bajo el mismo esquema de paralelismo para que la comparación entre ellos sea
interna y homogénea.

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

### Nota de ejecución

Los siete flujos corren en paralelo sobre la misma máquina. El límite de tiempo del solver
es de reloj, así que la contención de CPU reduce iteraciones de GLS: `wall_clock_sec` y
`t_metaheuristic_sec` **no son comparables** con barridos previos y no se usan para juzgar
nada. Los siete brazos corren bajo el mismo esquema y el mismo grado de paralelismo, así
que la comparación entre ellos sí es válida.

---

## Criterio de éxito (heredado, NO renegociable a posteriori)

- **n=1607:** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** `relleno_msf_sec` **−≥30 %** vs `actual`, cruces **sin
  empeorar**.
- **Global:** **0 drops**; **balance min/max ≥0.60** en **toda** instancia; **0 rutas
  degeneradas**, con la definición absoluta de siempre (**<5 paradas** O **<1 800 s**).

### Regla de varianza

Una diferencia entre brazos cuenta como **real** sólo si

```text
|media_A − media_B| > desv_A + desv_B
```

sobre las 5 semillas. Si no la supera se reporta como **empate**, explícitamente y con esa
palabra.

### Sobre qué se evalúa

Los criterios se evalúan sobre la **media** de las 5 réplicas. Además, y porque **la
hipótesis de este ciclo es sobre la cola**, se reporta la **peor réplica** para balance y
para rutas degeneradas. Un piso de cordura que sólo se cumple en promedio no es un piso, y
"0 degeneradas en media" con una réplica degenerada es exactamente el fallo que este ciclo
intenta cerrar.

---

## Trampa declarada por adelantado

Un piso de paradas puede **matar la degeneración por conteo empujando árboles a rutas donde
no corresponden geográficamente**. Eso no aparecería en la columna `degenerate_routes`:
aparecería como **más cruces** o **peor travel**, o como relleno de áreas degradado.

Compromiso, escrito antes de medir: el reporte publicará el **intercambio completo**
—cruces, travel y `relleno_msf` de cada brazo con barras de error— junto al conteo de
degeneradas. **No se declara victoria mirando sólo el conteo de degeneradas.** Un brazo con
0 degeneradas y cruces al alza es un brazo que falla el criterio, y se reportará como tal.

## Compromisos de reporte

1. Este pre-registro se **commitea antes de medir**, como los cinco anteriores de la serie.
2. El criterio **no se toca** una vez leídos los resultados.
3. **Si el resultado es negativo se reporta igual de fuerte que uno positivo.** Los mejores
   hallazgos de la serie salieron así; el ciclo de multi-arranque es el ejemplo más
   reciente.
4. La aritmética de la Fase 0 queda fijada arriba **con su predicción**, de modo que el
   barrido de fuerza pueda confirmarla o refutarla en vez de racionalizarla después.

---

## Reproducción

```bash
# Cargar la suite congelada (UUID deterministas, la cache de OSRM acierta)
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
  python manage.py load_instances

# Eje de umbral + controles (fuerza por defecto, 10 000)
for cell in actual feasible-floor-b095 \
            feasible-floor-b095-stops5 \
            feasible-floor-b095-stops10 \
            feasible-floor-b095-stops15; do
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv "docs/experiments/stops-penalty-sweep-20260722-$cell.csv" \
      --only-cell "$cell" --seeds 1 2 3 4 5 &
done

# Eje de fuerza (umbral 10 fijo)
for pen in 1000 100000; do
  docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv "docs/experiments/stops-penalty-sweep-20260722-stops10-pen$pen.csv" \
      --only-cell feasible-floor-b095-stops10 --stops-penalty "$pen" --seeds 1 2 3 4 5 &
done
wait
```

---

---

## Resultados

Datos: `stops-penalty-sweep-20260722-{actual,feasible-floor-b095,feasible-floor-b095-stops5,
feasible-floor-b095-stops10,feasible-floor-b095-stops15,stops10-pen1000,stops10-pen100000}.csv`.
**420 filas**: 7 brazos × 12 instancias × 5 semillas. **Drops = 0 en las 420 filas.**
Un CSV y un flujo por brazo, mismo grado de paralelismo para los siete.

### El resultado en una línea

**El piso de paradas no cierra el fallo de degeneración a ningún umbral ni a ninguna
fuerza, y cuesta travel.** La hipótesis del ciclo queda **falsada**.

### Rutas degeneradas — el criterio que este ciclo atacaba

| Brazo | degeneradas/réplica | réplicas con ≥1 | vs `b095` (regla de varianza) |
| --- | ---: | ---: | --- |
| `actual` | 0.0±0.0 | 0/5 | empate |
| `feasible-floor-b095` | 0.2±0.4 | 1/5 | — (base) |
| `b095+stops5` | 0.2±0.4 | 1/5 | **empate** |
| `b095+stops10` | 0.2±0.4 | 1/5 | **empate** |
| `b095+stops15` | 0.2±0.4 | 1/5 | **empate** |
| `b095+stops10` @ 1 000 | 0.0±0.0 | 0/5 | **empate** |
| `b095+stops10` @ 100 000 | 0.2±0.4 | 1/5 | **empate** |

**Los seis brazos empatan con `b095`.** Ni el umbral (5→10→15) ni la fuerza
(1 000→10 000→100 000) mueven la degeneración. El barrido de fuerza es una **meseta
plana**, que es exactamente la predicción pre-registrada en la Fase 0.

**El `0.0±0.0` de `b095+stops10 @ 1 000` no es una victoria y no se reporta como tal.**
Contra `0.2±0.4` de `b095`, la diferencia (0.2) no supera la dispersión (0.4): es un
**empate**. Además es el brazo con la penalización **más débil** —la que menos debería
poder arreglar nada—, lo que confirma que la lectura correcta es ruido y no efecto.
Leerlo como ganador sería exactamente el error de un solo punto que
`sweep-metrology-20260720` corrigió en toda la serie.

### Por qué el piso no puede tocar esa ruta

Las filas degeneradas siguen concentradas en `reference-n1607`, y siguen marcadas por
**conteo de paradas** (`dur_min` entre 8 475 y 9 269 s, muy por encima de 1 800 s).

Primer indicio: en la semilla 5, `b095+stops5`, `b095+stops10` y `b095+stops10 @ 100 000`
producen **métricas idénticas** —travel 64 728, cruces 18, `dur_min` 9 269, balance 0.862,
1 degenerada—. Un piso de 5 y uno de 10 paradas, cobrados a 10 000 y a 100 000, aterrizan
en la **misma solución**.

Volcado directo de esa solución (`reference-n1607`, semilla 5, `b095+stops10`), a las dos
fuerzas:

```text
k=25  drops=0
sizes: [3, 53, 56, 57, 57, 59, 61, 64, 65, 65, 65, 65, 67, 67, 68, 68, 69, 71, 73, 74, 74, 75, 76, 77, 78]
RUTA CORTA: 3 paradas, travel=10 125 s, duración=10 485 s
```

Idéntico a 10 000 y a 100 000 por parada faltante.

**La ruta degenerada tiene 3 paradas y 10 485 s de duración, contra un `T_max` de 10 800 s:
está al 97 % de su capacidad dura.** Son tres árboles aislados a ~2,8 h de camino de todo
lo demás. El piso de paradas cobra 7 × penalización y el solver **la paga**, porque el
arreglo que la penalización incentiva —meterle una cuarta parada— es **infactible bajo
`T_max`**, y sacar esos tres árboles a otra ruta choca con que las otras 24 llevan entre 53
y 78 paradas y también están cerca del techo.

**El piso es inerte sobre esa ruta por construcción, no por precio.** Añade una constante
al objetivo que ningún movimiento disponible puede reducir, así que no cambia el argmin y
subir la constante ×10 no cambia nada. Eso es lo que se ve en la meseta y en las
soluciones idénticas.

Esto **confirma por medición** lo que `sweep-metrology-20260720` cerró por aritmética: la
palanca queda **fuera del objetivo del VRP**. Lo único que mueve esta ruta es `T_max`, el
tiempo de servicio o la partición territorial previa — parámetros del problema, no términos
de penalización.

### El intercambio: qué cuesta el piso (la trampa pre-registrada, materializada)

`reference-n1607`, media ± desviación sobre 5 réplicas. Control `actual`:
cruces 77.6±11.7, travel 60 909±745, k 25.0±0.0.

| Brazo | k | cruces | Δ cruces | travel | Δ travel |
| --- | ---: | ---: | ---: | ---: | ---: |
| `feasible-floor-b095` | 25.0±0.0 | 22.4±5.0 | −71.1 % (real) | 62 751±1 062 | **+3.02 % (real)** |
| `b095+stops5` | 25.0±0.0 | 23.0±5.1 | −70.4 % (real) | 63 555±1 177 | **+4.34 % (real)** |
| `b095+stops10` | 25.0±0.0 | 24.4±4.9 | −68.6 % (real) | 64 782±976 | **+6.36 % (real)** |
| `b095+stops15` | 25.0±0.0 | 26.4±3.9 | −66.0 % (real) | 64 988±1 150 | **+6.70 % (real)** |
| `b095+stops10` @ 1 000 | 25.0±0.0 | 22.2±3.7 | −71.4 % (real) | 62 727±1 146 | +2.98 % (empate) |
| `b095+stops10` @ 100 000 | 25.0±0.0 | 24.6±5.1 | −68.3 % (real) | 64 481±999 | **+5.86 % (real)** |

**El travel crece de forma monótona con el piso**, y todos los brazos con piso efectivo
**fallan el criterio de travel ≤+3 %**: +4.3 %, +6.4 %, +6.7 %, +5.9 %. El único que no lo
falla es el de penalización 1 000, que es el que casi no aplica piso — y que por eso mismo
tampoco cambia nada.

Los cruces se mueven en la dirección mala (22.4 → 23.0 → 24.4 → 26.4 al apretar el umbral)
pero **ninguna de esas diferencias supera la regla de varianza contra `b095`: son empates**.
Se reportan igual, porque la tendencia es consistente en los tres umbrales y va en el
sentido que la trampa pre-registrada anticipaba.

**Así que el intercambio es el peor posible: el piso paga travel real y no compra nada.**
No es que compre menos degeneración de la esperada; es que compra **cero** degeneración
menos, medida con la regla de varianza, y cobra hasta +6.7 % de travel por ello.

El costo está concentrado en `reference-n1607`. En las otras once instancias los brazos con
piso son indistinguibles de `b095` en travel vs `actual` (`area-27` −73.9 %, `area-29`
−50.7 %, `battery-n400` −10.9 %, idénticos hasta la décima en todos los brazos). El piso
sólo binda donde `k` es
grande, y ahí paga sin arreglar.

### Relleno y cruces de áreas — sin cambios

`relleno_msf_sec`, media ± desviación, Δ vs `actual` (umbral pre-registrado −≥30 %):

| Brazo | `area-26-n157` | `area-27-n72` | `area-29-n43` |
| --- | ---: | ---: | ---: |
| `actual` (base) | 1 579±214 | 4 829±9 | 1 239±4 |
| `feasible-floor-b095` | 761±94 → −51.8 % | 195±8 → −96.0 % | 210±0 → −83.1 % |
| `b095+stops5` | 747±82 → −52.7 % | 195±8 → −96.0 % | 210±0 → −83.1 % |
| `b095+stops10` | 739±78 → −53.2 % | 195±8 → −96.0 % | 210±0 → −83.1 % |
| `b095+stops15` | 780±73 → −50.6 % | 195±8 → −96.0 % | 210±0 → −83.1 % |
| `b095+stops10` @ 1 000 | 756±89 → −52.1 % | 195±8 → −96.0 % | 210±0 → −83.1 % |
| `b095+stops10` @ 100 000 | 739±78 → −53.2 % | 195±8 → −96.0 % | 210±0 → −83.1 % |

Las diferencias contra `actual` son **reales** en las tres áreas y en los seis brazos; las
diferencias **entre** brazos con piso y `b095` son **empates**. Los cruces de áreas no
empeoran en ninguna: `area-27` pasa de 9.8±4.9 a 0.0±0.0 (real), `area-29` de 4.6±0.5 a
0.0±0.0 (real), `area-26` de 0.4±0.5 a 0.0–0.2 (empate).

El piso de paradas es, en las áreas chicas, **inocuo**: ni ayuda ni estorba. Ahí `k` es 1–3
y ninguna ruta se acerca al umbral de paradas.

### Balance

| Brazo | balance mín. (media por instancia) | instancias <0.60 en media | peor réplica | instancias <0.60 en peor réplica |
| --- | ---: | ---: | ---: | ---: |
| `actual` | 0.838 | **0** | 0.831 | **0** |
| `feasible-floor-b095` | 0.629 | **0** | 0.526 (`battery-n100`) | 2 |
| `b095+stops5` | 0.628 | **0** | 0.526 (`battery-n100`) | 2 |
| `b095+stops10` | 0.628 | **0** | 0.526 (`battery-n100`) | 2 |
| `b095+stops15` | 0.628 | **0** | 0.526 (`battery-n100`) | 2 |
| `b095+stops10` @ 1 000 | 0.629 | **0** | 0.526 (`battery-n100`) | 2 |
| `b095+stops10` @ 100 000 | 0.628 | **0** | 0.526 (`battery-n100`) | 2 |

Idéntico en los seis brazos, y idéntico a lo que midió `sweep-metrology-20260720`. El piso
de paradas **no toca el balance en ninguna dirección**: la peor réplica sigue en 0.526
sobre `battery-n100`, donde el problema no es el conteo de paradas.

---

## Estado de cada criterio

### `feasible-floor-b095-stops10` — la celda que faltaba

| Criterio | Resultado | ¿Pasa? |
| --- | --- | :---: |
| n=1607 cruces −≥30 % | −68.6 % (real) | ✅ |
| n=1607 travel ≤+3 % | **+6.36 % (real)** | ❌ |
| n=1607 k ≤26 | 25.0±0.0 | ✅ |
| Áreas: `relleno_msf` −≥30 % | −53.2 % / −96.0 % / −83.1 % | ✅ |
| Áreas: cruces sin empeorar | mejoran o empatan las tres | ✅ |
| Drops = 0 | 0 en 60 filas | ✅ |
| Balance ≥0.60 en toda instancia | 0 <0.60 en media; 2 en peor réplica (0.526) | ⚠️ |
| **0 rutas degeneradas** | **1 ruta en 1 de 5 réplicas** (empate con `b095`) | ❌ |

**Seis de ocho.** El piso de paradas **no quita** el fallo que atacaba y **agrega** uno
nuevo: travel. Es estrictamente peor que `b095`.

### `feasible-floor-b095` re-corrido en este ciclo — una corrección que hay que declarar

| Criterio | Este ciclo | `sweep-metrology-20260720` |
| --- | --- | --- |
| n=1607 cruces −≥30 % | −71.1 % (real) ✅ | −87.5 % (real) ✅ |
| n=1607 travel ≤+3 % | **+3.02 % (real)** ❌ | −0.6 % (empate) ✅ |
| n=1607 k ≤26 | 25.0±0.0 ✅ | 25.0±0.0 ✅ |
| Áreas: `relleno_msf` −≥30 % | −51.8 / −96.0 / −83.1 ✅ | −50.1 / −96.0 / −83.0 ✅ |
| Áreas: cruces sin empeorar | ✅ | ✅ |
| Drops = 0 | ✅ | ✅ |
| Balance ≥0.60 | 0 en media, 2 en peor réplica ⚠️ | 0 en media, 2 en peor réplica ⚠️ |
| 0 rutas degeneradas | 1 en 1/5 ❌ | 1 en 1/5 ❌ |

**`b095` mide aquí +3.02 % de travel, apenas por encima del umbral de +3 %, contra −0.6 %
en el ciclo anterior.** No se ajusta el criterio para acomodarlo: con estos números `b095`
**falla** travel por 0.02 puntos, y pasa de 7/8 a **6/8**.

Esto es un hallazgo por sí mismo, y va en contra del candidato: **las réplicas de semilla no
capturan toda la varianza.** Las cinco semillas de cada corrida dan barras de error de
±745 a ±1 062 s, pero la media de `b095` se movió de 59 971 a 62 751 s **entre corridas**,
un salto mayor que su propia desviación entre semillas. La regla de varianza pre-registrada
compara brazos **dentro** de una corrida, donde sigue siendo válida; **no** autoriza a
comparar cifras entre ciclos, y la serie debería dejar de hacerlo.

La lectura honesta: el margen de travel de `b095` es de **cola, no de media**, igual que su
degeneración. En un ciclo cae del lado bueno del umbral y en otro del lado malo.

---

## Veredicto

**La hipótesis del ciclo queda falsada.** Un piso de paradas sobre `b095` —a umbral 5, 10 o
15, y a fuerza 1 000, 10 000 o 100 000— **no elimina las rutas degeneradas en ninguna
réplica más que `b095` sin piso**: los seis brazos empatan con la línea base bajo la regla
de varianza. Y no sale gratis: el travel de `n=1607` sube de forma monótona con el piso
hasta **+6.7 %**, muy por encima del **+3 %** que permite el criterio.

**No hay ganadora verificada en este ciclo, y no se dice esa frase.** No se cambia ningún
default de producción.

### Lo que sí queda establecido

1. **La degeneración de `b095` es estructural, no tarifaria.** La ruta que la produce tiene
   **3 paradas y 10 485 s de duración contra un `T_max` de 10 800 s**: está al 97 % de su
   capacidad dura. Ninguna penalización por parada faltante puede arreglarla, porque el
   movimiento que incentiva —añadir paradas— es infactible. La prueba directa es que
   umbrales 5 y 10 y fuerzas 10 000 y 100 000 devuelven la **misma solución**, con las
   mismas métricas hasta el segundo.
2. **La aritmética de la Fase 0 acertó, y acertó antes de medir.** Se pre-registró que
   `STOPS_FLOOR_PENALTY = 10 000` **no** es blanda (≈130× el costo de absorber una parada
   vecina), que por tanto la hipótesis "los stops-floor previos fallaron porque el precio
   era barato" estaba muerta, y que si `b095+stops10` no cerraba el fallo entonces subir la
   fuerza tampoco lo haría, produciendo una **meseta**. Es exactamente lo que se midió.
   El barrido de fuerza no descubrió un umbral: confirmó que no hay ninguno.
3. **La familia de pisos queda cerrada también por este flanco.** `sweep-metrology-20260720`
   la cerró por relleno (piso inactivo en `area-26`) y por varianza; este ciclo cierra el
   último hueco de la grilla —`b095+stops10`, la celda que faltaba— y lo cierra en negativo.
   Con `multistart-sweep-20260721` descartando la búsqueda como causa, quedan descartadas
   las tres explicaciones que la serie tenía sobre la mesa: **no es ruido de búsqueda, no es
   un precio mal calibrado, y no es un umbral mal elegido.**
4. **La palanca está fuera del objetivo del VRP**, y ahora con evidencia directa y no sólo
   aritmética. Lo que crea la ruta de 3 paradas es la combinación de `T_max`, el tiempo de
   servicio y tres árboles a 2,8 h de camino del resto. Ninguno de los tres es un término
   de penalización.
5. **Las réplicas de semilla no capturan la varianza entre corridas.** El travel de `b095`
   se movió más entre ciclos que entre semillas dentro de un ciclo. La regla de varianza
   sigue valiendo **dentro** de una corrida; comparar medias entre reportes de ciclos
   distintos no está justificado, y este reporte es el primero de la serie en decirlo con
   un contraejemplo medido.

### Sobre la trampa declarada

Se declaró por adelantado que un piso de paradas podía matar la degeneración empujando
árboles donde no corresponden, y que eso aparecería como más cruces o peor travel. **Ocurrió
la mitad mala de la trampa y nada de la buena:** el travel empeoró de forma real y monótona
(+4.3 %, +6.4 %, +6.7 %), los cruces derivaron en la dirección mala (22.4 → 26.4, empates), y
la degeneración **no** se movió. No hubo victoria que declarar mirando sólo el conteo, y no
se declara ninguna.

### Adopción

Sin cambios. `b095+stops10` es **estrictamente peor** que `b095` y queda descartado.
`b095` sigue sin pasar el criterio completo —y en esta corrida falla dos criterios en vez
de uno—, así que **no se adopta**. Los defaults de producción (`spatial_term`,
`PenaltyConfig` actual, coeficiente de span espacial 3) quedan intactos.

---

## Reproducción de las cifras del veredicto

Además del barrido de la sección anterior, el volcado de la ruta degenerada:

```bash
docker compose run --rm --no-deps -e RUN_MIGRATIONS=false backend python manage.py shell -c "
from apps.datasets.instances import dataset_uuid
from apps.datasets.models import Dataset, Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.n_estimator import estimate_max_vehicles
from apps.optimization.solver import PenaltyConfig, build_open_matrix
from apps.optimization.strategies import solve_by_strategy

ds = Dataset.objects.get(id=dataset_uuid('reference-n1607'))
trees = sorted(Tree.objects.filter(dataset=ds, is_active=True), key=lambda t: t.id)
matrix = OSRMCostMatrixBuilder().build(trees)
pts = [(t.location.y, t.location.x) for t in trees]
mv = estimate_max_vehicles(build_open_matrix(matrix), len(trees) * 120, 7200)
for pen in (10_000, 100_000):
    routes, dropped = solve_by_strategy(
        'spatial_term', matrix, points=pts, min_route_time_sec=7200,
        max_route_time_sec=10800, service_time_sec=120, max_vehicles=mv,
        time_limit_sec=120, node_seed=5,
        penalties=PenaltyConfig(balance_arm='feasible-floor-b095-stops10',
                                stops_floor_penalty=pen))
    print(pen, 'k=%d drops=%d' % (len(routes), len(dropped)),
          sorted(len(r) for r in routes))
    short = min(routes, key=len)
    travel = sum(matrix[a][b] for a, b in zip(short[:-1], short[1:], strict=True))
    print('  RUTA CORTA: %d paradas, travel=%d s, duracion=%d s'
          % (len(short), round(travel), round(travel) + len(short) * 120))
"
```

`duracion = travel + 120 s × paradas` es la misma aritmética que usa el driver del barrido
para la columna `dur_min_sec`.
