# Barrido de `spatial_span_coef`

**Objetivo:** medir si `spatial_span_coef` (fijo en 3, sin ajuste explicado frente al canal
temporal, que domina el objetivo por dos órdenes de magnitud) tiene efecto real sobre auto-cruces,
o si es un coeficiente inerte que solo aparenta ajuste.

**Método:** `config_algorithm_sweep --only-cell actual --spatial-span-coef {0,3,10,30}
--seeds 1 2 3 --post-resequence`, 12 instancias congeladas (`docs/experiments/instances`), 3
semillas por punto. 144 filas, sin duplicados (`docs/experiments/spatial-span-20260730.csv`).

## Resultado — instancia de referencia ($n=1\,607$)

| coef | k | crossings\_road (media) | travel\_sec (media) | balance |
| --- | --- | --- | --- | --- |
| 0  | 24–25 | 39,7 | 57 352 | 0,874 |
| 3 (producción) | 25 | 34,3 | 58 948 | 0,839 |
| 10 | 25 | 46,0 | 59 081 | 0,830 |
| 30 | 25–26 | 48,0 | 58 781 | 0,802 |

`crossings_road` **no baja monótonamente con el coeficiente**: mejora de 0→3 (−13,6\,%, lejos del
umbral de aceptación del −30\,%) y luego empeora en 10 y 30, terminando por encima del propio
baseline sin penalización espacial. Ningún valor alcanza el criterio de decisión.

## Resultado — áreas reales y batería sintética

El patrón se repite fuera de la referencia: `battery-n800` y `battery-n1000` (las dos instancias
agregadas más densas de la batería, después de la propia referencia) también empeoran su
`crossings_road` respecto de no penalizar, en los tres valores probados y sin orden monótono entre
ellos (n800: 19,3→22,3→25,3→24,7; n1000: 21,3→43,7→30,7→37,7). Las áreas reales
(`area-26`, `area-27`, `area-29`) y las instancias
sintéticas de baja densidad no muestran un patrón consistente en ninguna dirección — ruido de
semilla domina sobre cualquier señal del coeficiente.

## Diagnóstico

El coeficiente penaliza la distancia haversine acumulada por vehículo
(`SetSpanCostCoefficientForAllVehicles` sobre la dimensión Distance), a un precio de
`coef` por metro. Contra el canal temporal —que en la instancia de referencia satura
($\overline{\text{sat}}=0,94$) y cobra hasta 501/s por encima del objetivo superior— un
coeficiente espacial de hasta 30 sigue siendo marginal: no alcanza a reordenar la búsqueda hacia
geometrías con menos auto-cruces, y en las instancias donde sí mueve algo, empuja en la dirección
equivocada porque penalizar el **span** total no distingue tramos que cruzan de tramos que no
cruzan — el mismo defecto de "no distingue relleno de viaje productivo" ya documentado para
`span-c100` sobre la dimensión temporal (sección de discusión de calidad de la tesis).

**Veredicto: el prior en contra se confirma.** `spatial_span_coef` no es una palanca útil para
reducir auto-cruces sobre calle a ningún valor probado; el default de producción (3) no es peor
que subirlo y en la instancia de referencia es el único punto que mejora sobre no penalizar en
absoluto, así que no hay caso para cambiarlo. Sin cambio de código de producción.

## Acción

- Queda cerrada la pregunta por el valor de `spatial_span_coef`: el coeficiente fue medido, no es
  un ajuste sin fundamento pendiente sino uno ya explorado y sin ganancia disponible.
- Sin cambio de código de producción ni de la tesis.
