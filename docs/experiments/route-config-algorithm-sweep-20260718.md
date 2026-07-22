# Barrido configuración × algoritmo × tamaño sobre la suite real congelada

**Fecha:** 2026-07-18
**Datos:** `route-config-algorithm-sweep-20260718.csv` (288 filas = 96 celdas × 3 repeticiones
nominales, donde una **celda** es un par instancia × configuración; toda cifra de este reporte
sale de ese CSV). Ojo con la columna `cell` del CSV: guarda solo el nombre de la
**configuración**, no la celda en el sentido de este reporte.

> **Corrección posterior — `sweep-metrology-20260720.md`.** Las cifras de este reporte se
> midieron con un instrumento con dos defectos. (1) Las columnas `seed` **no eran réplicas**: el
> driver escribía la semilla en el CSV pero nunca la pasaba al solver, así que toda "media sobre
> 3 semillas" promedia tres repeticiones de una misma configuración, no réplicas independientes, y
> **ninguna cifra tiene barras de error**. Las tres filas coinciden exactamente en 78 de las 96
> celdas; en las 18 restantes `travel_sec` varía hasta 3.5 % (peor caso
> `battery-sparse-n500`/`tmin-scaled`, en orden de semilla: 22 669 / 22 927 / 22 157 s),
> dispersión que viene del corte por *wall-clock* del GLS, no de la semilla. (2) `relleno_sec`
> mide sobre un cero inalcanzable y sesgado por instancia: en
> `area-26-n157` contaba como relleno un 47.9 % de geometría irreducible. Las filas siguen siendo
> mediciones válidas de una corrida; los **veredictos de relleno** y las comparaciones de pocos
> puntos porcentuales entre brazos, no. El re-juicio de estas filas contra una cota alcanzable
> está en `sweep-metrology-20260720-rejudge.csv` (columna `relleno_msf_sec`).

Todo el barrido corre por *overrides* de CLI (`route_audit --balance-arm --span-cost-coefficient`
y el driver `config_algorithm_sweep`). La configuración de producción del solver no se toca:
los brazos y el coeficiente de span son opt-in y su valor por defecto reproduce el comportamiento
actual bit a bit.

---

## Registro previo (fijado ANTES de correr — no renegociable a posteriori)

### Configuración censal de referencia

| Parámetro | Valor |
| --- | --- |
| Servicio por árbol | 120 s (2 min) |
| T_max | 10 800 s (3 h) |
| T_min | 7 200 s (2 h, default de producción) |
| Límite de tiempo del solver | heurístico `min(30 + 1.5·n, 120)` s |
| Semillas | 3 por celda (etiquetan la repetición; la varianza viene del *wall-clock* del solver) |

No son los defaults de la UI: son la configuración del censo real.

### Instancias (12)

Batería `{50, 100, 200, 400, 800, 1000}`, dispersas `{250, 500}`, áreas reales
`{157, 72, 43}` y `n=1607`. Todas en `docs/experiments/instances/`, cargadas con
`load_instances` (UUID deterministas → la caché OSRM acierta).

### Eje CONFIG (estrategia fija `spatial_term`)

| Brazo | Cota inferior blanda (fin de ruta) | Cota superior blanda | span Time |
| --- | --- | --- | --- |
| `actual` (default prod) | T_min=7200 @10000/s | midpoint(T_min,T_max) @500/s | 0 |
| `upper-tmax-tmin9000` | 9000 @10000/s | T_max @500/s | 0 |
| `tmin-scaled` | min(T_min, servicio_total/k̂) @10000/s | midpoint(floor,T_max) @500/s | 0 |
| `service-floor` | — (sin cota inferior) | midpoint(T_min,T_max) @500/s | 0 |
| `tmin-scaled+exempt-last` | igual a `tmin-scaled` salvo el vehículo residual (exento) | midpoint(floor,T_max) @500/s | 0 |
| `span-c100` | T_min=7200 @10000/s | midpoint(T_min,T_max) @500/s | **100** |

`k̂` = `max_vehicles` estimado (cota superior de flota). El span se aplica al **Time**
(`SetSpanCostCoefficientForAllVehicles`); con `fix_start_cumul_to_zero=True` el span de una
ruta ES su duración, así que penaliza Σ duración = servicio (fijo) + viaje. La celda `span-c100`
está incluida como **predicción nula esperada**: penalizar la duración total no distingue relleno
de viaje productivo y queda dominada por la presión de la cota inferior; se espera que NO mejore
frente al relleno. Por eso existen los brazos `tmin-scaled` / `service-floor` / `exempt-last`,
que atacan el relleno bajando o eximiendo el piso en vez de penalizar la duración.

### Eje ALGORITMO (config fija `actual`)

`spatial_term` · `global` · `greedy`. (`spatial_term`+`actual` es la configuración compartida con
el eje CONFIG.)

### Métricas por celda

k, viaje total, balance (dur, min/max), σ(T), cruces (auto-intersecciones), peor IoU de bbox
entre rutas, entrelazado por ruta, walk_ratio, drops, saturación media, saturación estimada
(`servicio_total/(k·T_max)`), relleno (`viaje − viaje_mín_est`, con `viaje_mín_est=(n−k)·viaje_NN_medio`),
déficit a priori (`Σ max(0, T_min − servicio_ruta)`) y tiempos por fase (OSRM / model_build /
first_solution / metaheurística / extracción + *wall-clock*).

### Criterio de decisión (fijado a priori — NO negociable a posteriori)

- **balance ≥ 0.80 SIEMPRE.** El balance se redefine excluyendo la ruta residual **solo** en el
  brazo `exempt-last` (documentado); en el resto incluye todas las rutas.
- **k ≤ 26** y **0 drops**.
- **n=1607:** cruces **−≥30 %** y viaje **≤ +3 %** frente a `actual`.
- **áreas reales:** cruces **sin empeorar** y `(dur_total − censo) −≥10 %` frente a `actual`.

### Hipótesis a testear

`span cost + soft upper = T_max` podría dar una **config única** para todos los regímenes sin
guard. Predicción del análisis previo: el span sobre Time es casi redundante contra el relleno,
así que la config única probablemente NO surja del span, sino (si acaso) de los brazos que
tocan el piso.

---

## Pipeline de humo

Antes del barrido completo se corrió una tanda de humo (las 8 celdas sobre `area-29-n43`,
1 semilla): las 8 poblaron todas las métricas, la transacción con *rollback* dejó la base
compartida limpia y los tiempos por fase quedaron registrados. Señales ya coherentes con la
teoría: `span-c100` con viaje idéntico a `actual` (nulo predicho), `global` con más cruces (30),
`upper-tmax` rellenando el área chica (+89 % viaje, 15 cruces). Recién ahí se lanzó el barrido
completo (96 celdas = 8 configuraciones × 12 instancias, 288 filas).

## Resultados

Cifras promediadas sobre las 3 filas de cada celda. Fuente: CSV versionado. `Δviaje` / `Δcruces`
son relativos a `actual` de la misma instancia.

### `reference-n1607` — el objetivo real (censo completo, denso)

| configuración | k | viaje | balance | cruces | IoU | walk | sat | relleno | Δviaje | Δcruces |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| actual | 25 | 60 566 | 0.83 | 89.0 | 0.348 | 0.24 | 0.94 | 33 510 | — | — |
| **upper-tmax-tmin9000** | 25 | 60 382 | 0.84 | **6.7** | 0.317 | 0.24 | 0.94 | 33 326 | **−0.3 %** | **−92.5 %** |
| tmin-scaled | 25 | 59 092 | 0.75 | 87.0 | 0.348 | 0.23 | 0.93 | 32 036 | −2.4 % | −2.2 % |
| service-floor | 34 | 96 388 | 0.12 | 36.7 | 0.765 | 0.33 | 0.79 | 69 485 | +59.1 % | −58.8 % |
| tmin-scaled+exempt-last | 25 | 59 086 | 0.79 | 87.0 | 0.348 | 0.23 | 0.93 | 32 030 | −2.4 % | −2.2 % |
| span-c100 | 24 | 58 273 | 0.84 | 65.3 | 0.330 | 0.23 | 0.97 | 31 199 | −3.8 % | −26.6 % |
| global | 24 | 54 798 | 0.84 | 86.7 | 0.661 | 0.22 | 0.95 | 27 724 | −9.5 % | −2.6 % |
| greedy | 24 | 63 071 | 0.93 | 102.0 | 0.730 | 0.25 | 0.99 | 35 997 | +4.1 % | +14.6 % |

`upper-tmax-tmin9000` es el **único** que cumple el criterio de n=1607 (cruces −92.5 % ≫ −30 %,
viaje −0.3 % ≤ +3 %, balance 0.84, k=25, 0 drops). Anclar la cota superior en T_max elimina
prácticamente todo el entrelazado **sin costo de viaje**, porque a esta densidad las rutas ya
saturan T_max (sat 0.94) y llenarlas hasta el tope no exige detours. `span-c100` mueve cruces
pero se queda en −26.6 % (span sobre Time ≈ nulo, como se predijo). `global` mantiene los cruces
(le falta el término espacial). `greedy` es el peor en cruces.

### Áreas reales (chicas, poco saturadas) — régimen opuesto

| instancia (n) | configuración | viaje | balance | cruces | Δviaje | Δcruces_abs |
| --- | --- | --: | --: | --: | --: | --: |
| area-26 (157) | actual | 4 962 | 0.88 | 0.0 | — | — |
| | upper-tmax-tmin9000 | 8 140 | 0.99 | 2.0 | **+64.0 %** | +2.0 |
| area-27 (72) | actual | 5 738 | 1.00 | 6.0 | — | — |
| | upper-tmax-tmin9000 | 9 332 | 1.00 | 27.0 | **+62.6 %** | +21.0 |
| area-29 (43) | actual | 2 022 | 1.00 | 0.0 | — | — |
| | upper-tmax-tmin9000 | 3 821 | 1.00 | 15.0 | **+89.0 %** | +15.0 |

En las áreas reales el brazo ganador de n=1607 es el **peor**: como no hay árboles suficientes para
llenar T_max, anclar arriba **fuerza relleno** (+62–89 % de viaje) y ese vagabundeo agrega cruces.
Y no hay problema que arreglar: bajo `actual` las áreas ya salen casi limpias (area-26: 0 cruces,
area-29: 0, area-27: 6). El entrelazado es un fenómeno **exclusivo del régimen denso** (n=1607: 89
cruces), y ahí `upper-tmax-tmin9000` lo arregla gratis.

### Compuerta dura balance ≥ 0.80 (SIEMPRE, sobre las 12 instancias)

| brazo | instancias con balance < 0.80 |
| --- | --- |
| actual | **0** |
| upper-tmax-tmin9000 | **0** |
| span-c100 | **0** |
| tmin-scaled | 7 (area-27, area-29, n1000, n400, n800, sparse-250, n1607) |
| tmin-scaled+exempt-last | 4 (n1000, n400, n800, n1607) — aun excluyendo la ruta residual |
| service-floor | 7 (area-27, n1000, n400, n50, n800, sparse-250, n1607) |

Los tres brazos que atacan el relleno bajando o eximiendo el piso (`tmin-scaled`, `service-floor`,
`tmin-scaled+exempt-last`) **rompen la compuerta de balance** en el régimen medio-denso: sin piso,
el solver deja rutas casi vacías. Quedan **descalificados como configuración universal**,
independientemente de su efecto sobre cruces. Solo `actual`, `upper-tmax-tmin9000` y `span-c100`
respetan balance ≥ 0.80 en todas las instancias.

### Por qué el régimen decide: saturación

El costo de viaje de `upper-tmax-tmin9000` es inverso a la densidad (capacidad de saturar T_max):

| instancia | sat (`actual`) | Δviaje upper-tmax | Δcruces upper-tmax |
| --- | --: | --: | --: |
| reference-n1607 | 0.94 | −0.3 % | −92.5 % |
| battery-n1000 | 0.91 | +7.7 % | −91.2 % |
| battery-n800 | 0.89 | +13.5 % | −82.6 % |
| area-26-n157 | 0.73 | +64.0 % | (0→2) |
| area-27-n72 | 0.67 | +62.6 % | (6→27) |
| area-29-n43 | 0.67 | +89.0 % | (0→15) |

Cuando la instancia satura T_max de forma natural (denso), anclar arriba es **gratis** y limpia
los cruces; cuando no puede (áreas chicas), anclar arriba **rellena** y ensucia. La saturación a
priori `servicio_total/(k̂·T_max)` es la variable de compuerta.

### Tiempos por fase (n=1607, promedio de las 3 filas por celda)

| configuración | osrm | model_build | first_solution | metaheurística | wall-clock |
| --- | --: | --: | --: | --: | --: |
| actual | 0.59 | 1.71 | 2.67 | 117.33 | 122.67 |
| upper-tmax-tmin9000 | 0.60 | 1.68 | 2.68 | 117.28 | 122.60 |
| global | 0.64 | 0.00 | 1.46 | 118.58 | 121.09 |
| greedy | 0.00 | 0.00 | 0.00 | 0.00 | 0.15 |

OSRM acierta en caché (~0.6 s); el costo es todo metaheurística, que consume el `time_limit`
completo (GLS corre hasta el tope de reloj). El brazo no cambia el perfil de tiempos: es un
cambio de objetivo, no de costo computacional.

## Decisión

**No existe una configuración única ganadora para todos los regímenes sin *guard*.** La hipótesis
—`span cost` + `soft upper = T_max` daría config única sin *guard*— queda **refutada** en sus dos
mitades:

1. **`span cost` sobre Time es casi nulo** (predicho): `span-c100` solo llega a −26.6 % de cruces
   en n=1607 (no alcanza el −30 %) y reordena sin estructura; penalizar Σ duración no distingue
   relleno de viaje productivo.
2. **`soft upper = T_max` NO es universal, es dependiente del régimen.** Gana n=1607 de forma
   decisiva y **gratuita** (cruces −92.5 %, viaje −0.3 %), pero es la peor opción en áreas chicas
   (+62–89 % de viaje por relleno).

Los brazos que atacaban el relleno (`tmin-scaled`, `service-floor`, `exempt-last`) quedan fuera por
**romper la compuerta de balance ≥ 0.80** en el régimen medio-denso.

**Recomendación — config con *guard* por régimen:**

- **Mantener `actual` como default de producción** (sin regresión; balance sano en todas las
  instancias; revertible). Las áreas chicas ya salen casi limpias con `actual` y no requieren nada.
- **Adoptar `upper-tmax-tmin9000` en el régimen denso / de alta saturación** (la corrida de censo
  completo, escala n=1607): recorta el 92 % del entrelazado a costo de viaje nulo, atacando de raíz
  la queja visual de rutas entrelazadas.
- **Compuerta:** aplicar `upper-tmax-tmin9000` cuando la saturación a priori
  `servicio_total/(k̂·T_max)` supere un umbral de alta saturación (los datos sugieren ≈0.9; n=1607
  a 0.94 lo cumple, las áreas a 0.67–0.73 no); en caso contrario, `actual`. Nunca aplicarlo a áreas
  poco saturadas: rellena y ensucia.
- **Descartar** `span-c100` (nulo), `tmin-scaled`, `service-floor`, `tmin-scaled+exempt-last`
  (rompen balance). `global` y `greedy` confirman que `spatial_term` es la estrategia correcta
  (ambos mantienen o empeoran los cruces).

El código de los *overrides* queda en el árbol (opt-in, producción intacta) para reproducir el
barrido y para habilitar la compuerta cuando se implemente el selector por saturación.

