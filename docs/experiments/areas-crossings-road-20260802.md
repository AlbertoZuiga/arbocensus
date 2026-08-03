# Serie de `crossings_road` sobre áreas reales (2026-08-02)

**Objetivo:** convertir en medición la observación cualitativa de la tesis según la cual, en el
régimen de área real, la configuración de producción "no muestra auto-cruces apreciables" y estos
"emergen al procesar el conjunto agregado". La serie sistemática de `crossings_road` por área
individual estaba declarada pendiente en las Secciones 4.1.4 y 4.2.1.

**Método:** `manage.py config_algorithm_sweep --csv docs/experiments/areas-crossings-road-20260802.csv
--only-instance {area-26-n157,area-27-n72,area-29-n43,areas-26-27-29-n272} --only-cell actual
--seeds 42 43 44 --post-resequence`. Configuración de producción (estrategia `spatial_term`,
`T_min` 7200 s, `T_max` 10800 s, servicio 2 min, límite de solver `min(30+1,5n, 120)` s, 2-opt
activo), tres semillas por instancia. La celda `areas-26-27-29-n272` exigió agregar la unión a la
lista `INSTANCES` del comando (estaba congelada en `docs/experiments/instances/` pero fuera de la
suite del barrido). `crossings_road` cuenta auto-cruces sobre la polilínea real de calles que
devuelve OSRM, la misma geometría que dibuja el mapa del censista. Comparación contra la corrida de
referencia unificada del mismo día (`reference-unified-20260802.csv`, misma configuración y
semillas).

## Resultado

| instancia | k | crossings_road (42/43/44) | media | por ruta | balance | drops |
| --- | --- | --- | --- | --- | --- | --- |
| area-26-n157 | 3 | 6 / 2 / 6 | 4,7 | 1,56 | 0,806–0,924 | 0 |
| area-27-n72 | 2 | 4 / 2 / 3 | 3,0 | 1,50 | 0,821–0,831 | 0 |
| area-29-n43 | 1 | 1 / 0 / 3 | 1,3 | 1,33 | 1,000 | 0 |
| areas-26-27-29-n272 | 5 | 10 / 7 / 6 | 7,7 | 1,53 | 0,878–0,933 | 0 |
| reference-n1607 (referencia) | 25 | 24 / 37 / 33 | 31,3 | 1,25 | 0,829–0,837 | 0 |

## Veredicto — la forma fuerte de la afirmación NO se sostiene

1. **"No muestra auto-cruces" es falso en sentido estricto.** Todas las instancias de área real
   muestran auto-cruces sobre calle en al menos una semilla; solo `area-29-n43` con la semilla 43
   registra cero. Los conteos absolutos por solución completa son bajos (0–6 en áreas
   individuales, 6–10 en la unión) frente a 24–37 en la instancia agregada.
2. **"Emergen al procesar el conjunto agregado" tampoco, como tasa.** Normalizado por ruta, el
   indicador es esencialmente plano en toda la serie: 1,33–1,56 en las áreas y su unión frente a
   1,25 en la agregada. La instancia agregada no produce más auto-cruces por ruta; produce más
   rutas (k=25 frente a k=1–5), y el conteo absoluto escala con ellas.
3. Lo que la serie sí sostiene: en la escala del área real una solución completa contiene del orden
   de 1–6 auto-cruces sobre calle, y en la unión de tres áreas 6–10, cifras absolutas un orden de
   magnitud por debajo de la instancia de estrés.

## Acción

- Los tres pasajes de reserva cualitativa de la tesis (4.1.4 ×2 y 4.2.1) se reemplazan por la
  cifra medida y la afirmación se corrige: escasos en absoluto, tasa por ruta comparable.
- La conclusión sobre la unidad operativa (área de censo) queda sostenida por el precio medido de
  la partición y el correlato operativo, no por una supuesta ausencia de auto-cruces en áreas.
