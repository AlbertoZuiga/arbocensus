# Diagnóstico de `area-26-n157` y barrido del piso combinado (duración escalada + paradas)

**Fecha:** 2026-07-20
**Datos:** `combined-floor-sweep-20260720.csv` (barrido) y
`combined-floor-diagnostic-20260720.csv` (diagnóstico).

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual, coeficiente
de span espacial 3) intactos. Los brazos nuevos son opt-in.

Este reporte cierra el ciclo abierto por `stops-floor-sweep-20260720.md`, cuyo veredicto fue:
el piso de paradas mata las rutas stub sin comprar relleno (mecanismo confirmado) pero no da
balance, porque diez paradas juntas pueden durar una hora; `feasible-floor-b095` sigue siendo
el único brazo que compra balance y no-degeneración a la vez, y falla **solo** el relleno de
`area-26-n157`. Ese reporte dejó anotadas dos cosas sin medir, y las dos se miden acá:

1. `area-26-n157` es la instancia que ningún brazo arregla —tres ciclos consecutivos fallaron
   el mismo criterio en la misma instancia—, y nunca se verificó si el criterio es
   **alcanzable** en ella.
2. Un piso **combinado** (conteo de paradas como cota anti-stub + piso de duración escalado
   como término de balance) es la composición natural de los dos resultados, y no se midió.

El orden importa: **el diagnóstico se corre y se resuelve primero**, porque si el criterio de
relleno de `area-26-n157` resulta inalcanzable, seguir agregando brazos de piso es correr
contra un objetivo imposible.

---

## Parte A — Diagnóstico de `area-26-n157`

### Hipótesis a falsar

El relleno de `area-26-n157` es **estructural**, no un artefacto del piso: la instancia
resuelve con un k̂ de más, de modo que k̂·(cualquier piso) excede el trabajo disponible, y
ninguna penalización puede crear trabajo que no existe. Si es así, la palanca no es el piso
sino **k**, y los ciclos anteriores vinieron fallando contra un objetivo inalcanzable.

Motivación cuantitativa, leída del CSV del ciclo anterior
(`stops-floor-sweep-20260720.csv`, medias de 3 semillas sobre `area-26-n157`):

| Celda | k | travel | relleno |
| --- | ---: | ---: | ---: |
| `actual` | 3.0 | 4 962 | 2 579 |
| `no-floor` | 3.0 | 4 300 | 1 917 |
| `feasible-floor-b095` | 3.0 | 4 425 | 2 042 |

**k = 3.0 en las diez celdas medidas del ciclo anterior, sin excepción.** Ningún brazo movió
k jamás. Y `no-floor` —sin ningún piso de duración, es decir, con el mecanismo causal del
relleno completamente apagado— deja el 74 % del relleno del control. Eso ya sugiere que el
residuo no es padding inducido por el piso, sino otra cosa; el diagnóstico lo decide con
aritmética en vez de con sospecha.

### Definiciones y cotas (fijadas antes de medir)

Notación: `n` nodos, `k` rutas abiertas, servicio `s = 120 s/árbol`, `T_max = 10 800 s`,
`nn̄` = media de la distancia al vecino más cercano (la misma que usa el driver).

El driver define **relleno** como el exceso de travel sobre una cota inferior de vecino más
cercano:

```
relleno := travel_total − (n − k) · nn̄
```

Sobre esa definición se fijan tres cotas, todas verificables:

- **(LB-geom) Cota geométrica.** Un conjunto de `k` caminos abiertos que cubre los `n` nodos
  es un bosque generador de `n − k` aristas y `k` componentes. Por lo tanto
  `travel_total ≥ MSF_k`, el bosque generador mínimo de `k` componentes (= MST menos las
  `k − 1` aristas más pesadas). Se calcula sobre la matriz simetrizada `min(d_ij, d_ji)`, lo
  que sólo puede subestimar el costo dirigido: la cota sigue siendo válida.
- **(LB-piso) Cota inducida por el piso.** Si toda ruta termina en `≥ F`, entonces
  `travel_total ≥ k · F − n · s`.
- **(UB-tmax) Techo de factibilidad.** Toda ruta cumple `≤ T_max`, así que
  `travel_total ≤ k · T_max − n · s`. Si el techo es menor que `MSF_k`, ese `k` es
  **infactible** y el solver no puede elegirlo.

De donde, para cada `k`, la cota inferior de relleno que ese `k` impone:

```
relleno_LB(k, F) = max(LB-geom, LB-piso) − (n − k) · nn̄
```

### Mediciones

1. **Descomposición** de `area-26-n157`: `n`, servicio total, `nn̄`, `MSF_k` para
   `k ∈ {1, 2, 3, 4}`, saturación a priori `n·s / (k·T_max)`, techo `UB-tmax` por `k`, y
   `relleno_LB(k, F)` para el piso de producción y para piso nulo.
2. **Frontera relleno-vs-balance:** grilla `beta ∈ {0.50, 0.60, 0.70, 0.85, 0.95}` del piso
   factible, **sólo en esta instancia** (hoy sólo existen `b085`/`b090`/`b095`; se agregan los
   beta bajos). Pregunta: ¿existe algún beta con relleno **−≥50 %** *y* balance **≥0.60**?
3. **Palanca nunca probada acá — k forzado.** Resolver con exactamente `k_observado − 1 = 2`
   vehículos, sin buffer. Si el relleno desaparece con `k−1`, queda probado que era exceso de
   vehículos; si resulta infactible o produce drops, queda probado que `k = 3` es forzado por
   `T_max` y que el relleno con `k = 3` es un piso estructural.

### Regla de reescritura del criterio (fijada antes de medir)

Una **imposibilidad medida** es un resultado válido, no un fracaso. Si y sólo si el
diagnóstico demuestra que `relleno_LB(k, F) > 0.5 · relleno_actual` para todo `k` factible,
el criterio de relleno de `area-26-n157` se reescribe **contra esa cota medida**, se deja
registrada la aritmética que lo respalda y el cambio se commitea **antes de correr el barrido
de la Parte B**. Fuera de ese caso el criterio heredado no se toca. En ningún caso se
renegocia un criterio después de mirar resultados del barrido.

---

## Parte B — Barrido del piso combinado

### Hipótesis

Un piso de **duración escalado a la instancia** es lo que compra balance (es el único
mecanismo que lo logró en toda la serie). Un piso de **paradas** es lo que prohíbe rutas stub
sin comprar relleno (mecanismo ya confirmado). Hoy son mutuamente excluyentes en el código:
cada uno se activa por el prefijo del nombre del brazo. **Compuestos**, un beta **bajo**
(0.60–0.70, nunca probado: la grilla existente sólo llega a 0.85) dejaría el piso de duración
holgado —y por lo tanto sin relleno—, mientras el piso de paradas impediría los stubs que ese
beta bajo habilitaría. Sería el primer brazo que compra los dos criterios que ningún brazo
simple compra junto.

### Brazos

Estrategia `spatial_term`, 3 semillas, suite completa de 12 instancias.

| # | Brazo | Mecanismo |
| --- | --- | --- |
| 1 | `feasible-floor-b{060,070,085}-stops10` | Piso de duración escalado `T_min_eff = min(T_min, β·trabajo_total/k_est)` **más** dimensión unitaria `Stops` con cota blanda inferior de 10 paradas por ruta activa, penalidad 10 000 por parada faltante. |

Controles, todos ya medidos en `stops-floor-sweep-20260720.csv` y releídos de ahí (cero
cómputo): `actual`, `feasible-floor-b095`, `no-floor-stops10`.

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s (2 min) |
| T_max | 10 800 s (3 h) |
| T_min | 7 200 s (2 h, default de producción) |
| Límite de tiempo del solver | heurístico `min(30 + 1.5·n, 120)` s |
| Semillas | 3 por celda |

### Instancias

Batería `{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales
`{157, 72, 43}` y `n=1607`. Cargadas con `load_instances` (UUID estables, cache OSRM acierta).

---

## Criterio de éxito a priori (heredado — no renegociable a posteriori)

Idéntico al del ciclo anterior, salvo la eventual reescritura del relleno de `area-26-n157`
que habilita la regla de la Parte A:

- **n=1607 (denso saturado):** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** relleno (`relleno_sec`) **−≥50 %** vs `actual`, cruces **sin
  empeorar**.
- **Global:** **0 drops**, **balance min/max ≥0.60** en toda instancia, y **0 rutas
  degeneradas**.
- **Ruta degenerada — definición ABSOLUTA:** menos de **5 paradas** O duración menor a
  **1 800 s**. Ambos umbrales absolutos, idénticos a los del ciclo anterior, de modo que la
  columna `degenerate_routes` es comparable con `stops-floor-sweep-20260720.csv`.
- σ(T) y balance se reportan en todas las celdas aunque el balance no sea criterio duro más
  allá del piso de cordura 0.60.
- **Head-to-head final** de la mejor celda contra `feasible-floor-b095`, `no-floor-stops10` y
  `actual`.

Los criterios se evalúan sobre la media de las 3 semillas, no sobre el peor caso.

### Nota de ejecución

Las celdas se corren en flujos paralelos sobre la misma máquina. El límite de tiempo del
solver es de reloj, así que la contención de CPU reduce iteraciones de GLS. Las columnas
`wall_clock_sec` y `t_metaheuristic_sec` no son comparables con las de barridos previos; los
controles releídos del CSV anterior se corrieron bajo el mismo esquema.

---

## Resultados

_Pendiente: este reporte se commitea con hipótesis, grilla y criterio **antes** de correr._
