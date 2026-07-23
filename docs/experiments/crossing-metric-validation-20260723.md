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
