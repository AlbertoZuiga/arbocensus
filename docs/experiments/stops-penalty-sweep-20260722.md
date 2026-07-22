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

```
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

```
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
