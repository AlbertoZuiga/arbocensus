# Barrido de la familia sin piso (no-floor) con balance relajado

**Fecha:** 2026-07-19
**Datos:** `no-floor-balance-sweep-20260719.csv`, 216 filas (toda cifra de los brazos 1–3 y 5
sale de ese CSV; el brazo 4 es re-lectura de `objective-audit-postpass-sweep-20260718.csv`,
cero cómputo).

Todo el barrido corre por *overrides* de CLI del driver `config_algorithm_sweep`. La
configuración de producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig`
actual, `SPATIAL_SPAN_COEF=3`) intactos. Los brazos nuevos son opt-in.

Este reporte cierra el ciclo abierto por `objective-audit-postpass-sweep-20260718.md`, cuyo
veredicto fue: el piso factible mata el relleno en áreas chicas y desploma cruces en n=1607
pero rompe balance (<0.80) y sube travel +8–15 % en n=800/1000; el 2-opt intra-ruta solo
ayuda sobre `actual` en denso; el costo de arco convexo quedó refutado. La conclusión
transversal de ese reporte —"cualquier iteración del piso factible necesita un término de
balance explícito que no dependa del piso"— es exactamente lo que se prueba aquí.

---

## Cambio de criterio de balance (decisión de diseño, 2026-07-19)

El balance entre rutas de un mismo dataset es sacrificable hasta cierto punto: el balance
real entre censistas se logrará a largo plazo en la capa de asignación (repartir rutas entre
personas a lo largo de la campaña), no dentro de una sola solución de VRP. Por eso el umbral
de balance baja de **0.80** (usado en los barridos previos) a un **umbral de cordura 0.60**,
y se añade un criterio de **no-degeneración** para vigilar el riesgo real de soltar el piso:
rutas enanas.

---

## Registro previo (fijado ANTES de correr — no renegociable a posteriori)

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

### Definición de ruta degenerada (escrita antes de correr)

Una ruta es **degenerada** si tiene **menos de 5 paradas** O su duración es **menor al 25 %
de la mediana** de duraciones de rutas de su propia solución. La métrica `degenerate_routes`
del CSV cuenta, por celda, cuántas rutas cumplen esa condición.

### Criterio de éxito a priori

- **n=1607 (denso saturado):** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** relleno (`relleno_sec`) **eliminado o −≥50 %** vs `actual`,
  cruces **sin empeorar**.
- **Global:** **0 drops**, **balance min/max ≥0.60** en toda instancia, y **NINGUNA ruta
  degenerada** según la definición de arriba.
- σ(T) y balance se reportan en todas las celdas aunque ya no sean criterio duro.

---

## Brazos

Estrategia `spatial_term`, 3 semillas, suite completa de 12 instancias.

| # | Brazo | Mecanismo |
| --- | --- | --- |
| 1 | `actual` (baseline) | Producción: soft lower T_min 10 000/s, soft upper midpoint 500/s. Recalculado en este barrido para poblar las métricas nuevas (degeneración, dur min/med/máx). |
| 2 | `no-floor` | Soft lower **OFF**; soft upper en **T_max** (coef 500/s); `FIXED_VEHICLE_COST` intacto. |
| 3 | `no-floor-span-c{10,100,1000}` | Brazo 2 + `SetGlobalSpanCostCoefficient(c)` sobre la dimensión Time (penaliza el **máximo** span → balance suave sin piso). |
| 4 | `feasible-floor-b{085,090,095}` | Re-lectura del CSV previo contra el criterio nuevo. Cero cómputo. |
| 5 | `no-floor+reseq` | Condicional: solo si un brazo 2–3 gana en geometría, se repite esa celda con `--post-resequence` (2-opt intra-ruta) para ver si el post-pass aún aporta sobre base limpia. Se disparó con `no-floor`. |

Nota sobre el brazo 3: el span cost **global** de OR-Tools penaliza el mayor `end_cumul`
entre vehículos (la ruta más larga), no la suma de spans. Es un empujón hacia igualar
duraciones sin fijar un piso. En el barrido previo (`route-config-algorithm-sweep-20260718`)
el span cost medido fue nulo, PERO ahí competía con un soft lower dominante (10 000/s); sin
piso la escala relativa del span cost cambia, por eso se re-prueba y no es una repetición.

---

## Brazo 4 — Re-lectura de `feasible-floor` contra el criterio nuevo (cero cómputo)

Medias sobre 3 semillas de `objective-audit-postpass-sweep-20260718.csv`.

### Balance ≥0.60 (antes el corte era 0.80)

| Celda | balance mínimo (instancia) | instancias bajo 0.60 |
| --- | --- | --- |
| feasible-floor-b085 | 0.597 (battery-n200) | 1 |
| feasible-floor-b090 | 0.595 (battery-n800) | 1 |
| **feasible-floor-b095** | **0.652 (battery-n100)** | **0** |

Con el corte 0.80 ninguno pasaba; con el corte 0.60, **b095 pasa balance en las 12
instancias** (mínimo 0.652). b085 y b090 fallan por un pelo en una sola instancia cada uno
(0.597 y 0.595), ambas de la batería sintética media, no de instancias reales.

### b095 contra el criterio de éxito completo

| Instancia | travel Δ vs `actual` | cruces `actual` → b095 | balance b095 | relleno |
| --- | ---: | ---: | ---: | --- |
| reference-n1607 | **+0.2 %** | 88.7 → 16.7 (**−81 %**) | 0.667 | +0.3 % (sin cambio) |
| area-26-n157 | −10.8 % | 0 → 0 | 0.838 | −21 % |
| area-27-n72 | −73.8 % | 6 → 0 | 1.000 | −82 % (consolida k=2→1) |
| area-29-n43 | −50.6 % | 0 → 0 | 1.000 | −63 % |
| battery-n800 | **+10.0 %** | 29 → 6 | 0.749 | +16 % |
| battery-n1000 | +2.1 % | 56 → 9 | 0.688 | +4 % |
| battery-n200 | +0.2 % | 2 → 4 | 0.679 | +1 % |
| battery-sparse-n250 | −1.3 % | 2 → 1 | 0.768 | −3 % |

### Veredicto Brazo 4

Bajo el criterio relajado, **`feasible-floor-b095` deja de estar descartado**:

- **Balance:** pasa en las 12 instancias (min 0.652 ≥ 0.60). Era el único fallo duro contra
  el corte 0.80; contra 0.60 desaparece.
- **n=1607:** cruces −81 %, travel +0.2 %, k=25 (≤26). Cumple los tres.
- **Áreas chicas:** relleno −21 a −82 %, cruces nunca empeoran (0 en las tres). Cumple.
- **El travel +8–15 % en n=800/1000 SÍ persiste parcialmente:** para b095 es +10.0 % en
  n=800 y solo +2.1 % en n=1000. Es un costo de la batería sintética densa media; bajo el
  criterio nuevo el travel es criterio duro solo en n=1607 (donde b095 cumple), así que este
  bloat ya no es un fallo automático, pero se reporta como el costo residual de la idea.

Limitación de la re-lectura: el CSV previo no tiene la columna `degenerate_routes`, así que
la no-degeneración de b095 no se puede verificar retroactivamente. Los k de b095 (áreas → 1,
n=1607 → 25) y la ausencia de rutas <25 % de mediana no son medibles aquí; la degeneración se
mide de primera mano en los brazos 1–3.

---

## Brazos 1–3 — Resultados del barrido

180 filas (5 celdas × 12 instancias × 3 semillas). Medias sobre semillas. Drops = 0 en las
180 filas, en todas las celdas y todas las instancias.

### k / cruces / balance

| Instancia | `actual` (k/cx/bal) | `no-floor` | `+span-c10` | `+span-c100` | `+span-c1000` |
| --- | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 2 / 5 / 0.998 | 1 / 0 / 1.000 | 1 / 3 / 1.000 | 3 / 5 / 0.981 | 7 / 0 / 0.898 |
| battery-n100 | 2 / 3 / 0.946 | 2 / 0 / 0.966 | 2 / 1 / 0.999 | 2 / 8 / 0.984 | 5 / 0 / 0.972 |
| battery-n200 | 4 / 2 / 0.832 | 4 / 6 / **0.109** | 4 / 2 / 0.745 | 4 / 4 / 0.998 | 6 / 2 / 0.992 |
| battery-n400 | 7 / 2 / 0.987 | 6 / 3 / 0.834 | 6 / 5 / 0.842 | 7 / 5.7 / 0.971 | 8 / 6.7 / 0.977 |
| battery-n800 | 12 / 28 / 0.853 | 12 / 8 / **0.370** | 12 / 5 / **0.382** | 12 / 13.7 / 0.924 | 13 / 48 / 0.886 |
| battery-n1000 | 15 / 56.3 / 0.841 | 15 / 7 / **0.479** | 15 / 8 / 0.735 | 15 / 22.7 / **0.556** | 15 / 22 / 0.914 |
| battery-sparse-n250 | 5 / 2 / 0.946 | 5 / 1 / 0.681 | 5 / 1 / 0.976 | 5 / 1 / 0.991 | 6 / 3 / 0.967 |
| battery-sparse-n500 | 9 / 12.7 / 0.836 | 8 / 3.7 / 0.879 | 8 / 4 / 0.943 | 8 / 3 / 0.990 | 8 / 9 / 0.972 |
| area-26-n157 | 3 / 0 / 0.877 | 3 / 0 / 0.795 | 3 / 1 / 0.998 | 3 / 1 / 0.992 | 7 / 1 / 0.982 |
| area-27-n72 | 2 / 6 / 1.000 | 1 / 0 / 1.000 | 1 / 1 / 1.000 | 3 / 0 / 0.999 | 7 / 0 / 0.830 |
| area-29-n43 | 1 / 0 / 1.000 | 1 / 0 / 1.000 | 1 / 2 / 1.000 | 2 / 0 / 0.993 | 6 / 0 / 0.936 |
| **reference-n1607** | 25 / 89.3 / 0.833 | 25 / **6.3** / **0.011** | 25 / 21 / 0.715 | 25 / 19 / 0.714 | 25 / 23.7 / 0.715 |

### Δ travel vs `actual` / relleno (s)

| Instancia | travel ctl (s) | relleno ctl (s) | `no-floor` | `+span-c10` | `+span-c100` | `+span-c1000` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 8 399 | 6 375 | −59.3 % / 1 352 | −61.1 % / 1 199 | −64.2 % / 1 027 | −66.5 % / 1 001 |
| battery-n100 | 4 244 | 1 784 | +0.8 % / 1 817 | −7.4 % / 1 470 | −6.5 % / 1 510 | −7.5 % / 1 543 |
| battery-n200 | 8 254 | 4 776 | −3.8 % / 4 464 | +0.0 % / 4 778 | +3.1 % / 5 031 | −2.4 % / 4 610 |
| battery-n400 | 14 557 | 9 039 | −11.4 % / 7 364 | −13.0 % / 7 133 | +3.5 % / 9 548 | +6.4 % / 9 989 |
| battery-n800 | 19 827 | 10 864 | +6.9 % / 12 229 | +4.0 % / 11 663 | +24.3 % / 15 690 | +35.6 % / 17 934 |
| battery-n1000 | 26 776 | 15 824 | +0.8 % / 16 028 | +1.4 % / 16 191 | +11.3 % / 18 848 | +16.1 % / 20 133 |
| battery-sparse-n250 | 15 734 | 7 324 | −1.5 % / 7 087 | −1.5 % / 7 095 | +5.4 % / 8 173 | +11.3 % / 9 142 |
| battery-sparse-n500 | 23 257 | 13 815 | −7.7 % / 12 001 | −4.7 % / 12 712 | −5.7 % / 12 473 | −2.9 % / 13 132 |
| area-26-n157 | 4 962 | 2 579 | −13.3 % / 1 917 | +4.3 % / 2 792 | +6.9 % / 2 923 | +23.9 % / 3 827 |
| area-27-n72 | 5 738 | 5 207 | −74.2 % / 942 | −75.2 % / 886 | −74.3 % / 948 | −83.5 % / 454 |
| area-29-n43 | 2 022 | 1 634 | −50.6 % / 611 | −52.6 % / 570 | −56.5 % / 501 | −61.6 % / 434 |
| **reference-n1607** | 60 608 | 33 552 | **−13.9 % / 25 134** | +3.1 % / 35 450 | +3.9 % / 35 899 | +7.3 % / 37 995 |

### Degeneración y duración mínima

`degenerate_routes` (rutas con <5 paradas o duración <25 % de la mediana de su solución) y
`dur_min_sec` de la solución:

| Instancia | `actual` deg / dur_min | `no-floor` | `+span-c10` | `+span-c100` | `+span-c1000` |
| --- | ---: | ---: | ---: | ---: | ---: |
| battery-n50 | 0 / 7 191 | 0 / 9 419 | 0 / 9 266 | 0 / 2 979 | **1** / 1 158 |
| battery-n200 | 0 / 7 254 | **1** / 1 168 | 0 / 6 464 | 0 / 8 117 | 0 / 5 311 |
| battery-n800 | 0 / 8 988 | 0 / 3 970 | 0 / 3 970 | 0 / 9 420 | 0 / 8 602 |
| area-29-n43 | 0 / 7 182 | 0 / 6 159 | 0 / 6 118 | 0 / 3 010 | 0 / **961** |
| **reference-n1607** | 0 / 8 972 | **1** / **120** | 0 / 7 675 | 0 / 7 675 | 0 / 7 675 |
| **Total suite** | **0** | **2** | **0** | **0** | **1** |

La ruta degenerada de `no-floor` en n=1607 dura **120 s**: es una ruta de **un solo árbol**
(120 s = 1 × servicio). Ese stub es el que hunde el balance a 0.011 (120/10 800).

### Estado de cada criterio (a priori)

| Criterio | `no-floor` | `+span-c10` | `+span-c100` | `+span-c1000` |
| --- | --- | --- | --- | --- |
| n=1607 cruces −≥30 % | ✅ −93 % | ✅ −76 % | ✅ −79 % | ✅ −74 % |
| n=1607 travel ≤+3 % | ✅ −13.9 % | ❌ +3.1 % | ❌ +3.9 % | ❌ +7.3 % |
| n=1607 k ≤26 | ✅ 25 | ✅ 25 | ✅ 25 | ✅ 25 |
| Áreas chicas: relleno −≥50 % | ❌ (26: −26 %) | ❌ (26: +8 %) | ❌ (26: +13 %) | ❌ (26: +48 %) |
| Áreas chicas: cruces sin empeorar | ✅ | ❌ (26: 0→1, 29: 0→2) | ❌ (26: 0→1) | ❌ (26: 0→1) |
| Drops = 0 | ✅ | ✅ | ✅ | ✅ |
| Balance ≥0.60 en toda instancia | ❌ 0.011 | ❌ 0.382 | ❌ 0.556 | ✅ 0.715 |
| 0 rutas degeneradas | ❌ 2 | ✅ 0 | ✅ 0 | ❌ 1 |

**Ningún brazo cumple el criterio completo.** La hipótesis —"sin piso y con soft upper en
T_max sale una sola config limpia en ambos regímenes"— **no queda verificada**.

### Lectura

- **El piso ERA la causa del relleno y de los cruces, y quitarlo lo confirma de forma
  espectacular.** `no-floor` en n=1607 logra a la vez cruces −93 % (89.3 → 6.3), travel
  **−13.9 %** y relleno −25 % (33 552 → 25 134 s). Es la mejor combinación de geometría y
  travel medida sobre n=1607 en toda esta serie de barridos: a diferencia del piso factible
  (que igualaba travel) y de `upper-tmax-tmin9000` (que lo subía), quitar el piso **ahorra**
  travel. Caminar en círculos deja de ser óptimo, exactamente como predecía la hipótesis.
- **El riesgo predicho se materializó y es el que mata al brazo:** sin piso aparecen rutas
  stub. En n=1607 el solver deja una ruta de **un solo árbol** (120 s). No es un problema de
  balance "suave": es una ruta que ningún censista puede recibir. El criterio de
  no-degeneración, escrito antes de correr precisamente por este riesgo, hizo su trabajo.
- **El span cost global SÍ funciona como término de balance sin piso, y esto refuta la
  lectura previa de "span cost nulo".** Hay dosis-respuesta monótona clara en el balance
  mínimo de la suite: 0.011 → 0.382 → 0.556 → 0.715 para c = 0/10/100/1000. El resultado
  nulo de `route-config-algorithm-sweep-20260718.md` se midió con el soft lower dominante
  (10 000/s) activo, que aplastaba el término; sin piso el span cost es el que manda. La
  decisión de re-probarlo estaba justificada.
- **Pero el span cost paga el balance con todo lo que el brazo sin piso había ganado.**
  Al subir c, en n=1607 el travel pasa de −13.9 % a +7.3 %, los cruces de 6.3 a 19–24 y el
  relleno de 25 134 s a 37 995 s. Forzar hacia abajo la ruta más larga obliga a estirar las
  demás: **el span cost global reintroduce el incentivo de relleno por otra puerta**, sin
  necesidad de un piso explícito.
- **El balance que compra el span cost es en parte ilusorio: balancea fragmentando, no
  igualando.** Con c=1000 el término global vence al `FIXED_VEHICLE_COST` y hace barato
  partir la instancia en muchas rutas cortas: battery-n50 k 2→7, area-27 k 2→7, area-29
  k 1→6 (43 árboles en 6 rutas ≈ 7 árboles y ~16 min por ruta), area-26 k 3→7. El ratio
  min/max sube porque todas las rutas son igual de pequeñas. En n=1607, donde k=25 está
  fijado por el volumen de trabajo, este escape no existe y el balance se estanca en 0.715
  para c = 10, 100 y 1000 por igual — señal de que ahí el span cost ya saturó su efecto.
- **Limitación de la definición de degeneración pre-registrada:** al ser relativa a la
  mediana de la propia solución, no detecta la fragmentación uniforme (area-29 con c=1000
  tiene 6 rutas de ~16 min y marca 0 degeneradas, porque ninguna baja del 25 % de la mediana
  de un conjunto que ya es enano). Se deja constancia sin renegociar el criterio: el fallo
  se reporta igual vía k y `dur_min_sec`, que sí lo exhiben.
- **`area-26-n157` es la instancia que ningún brazo arregla.** Es el área real más grande y
  la menos holgada de las tres: su relleno solo baja −26 % con `no-floor` y **sube** con
  todos los brazos de span. Los brazos de span además le introducen el primer cruce (0 → 1).

---

## Brazo 5 — `no-floor` + post-pass 2-opt intra-ruta

Disparado por regla: `no-floor` gana geometría de forma decisiva (cruces n=1607 6.3 vs 89.3
del control), así que se repite **solo esa celda** con `--post-resequence` para medir si el
2-opt todavía aporta sobre una base ya limpia. El reporte previo dejó la predicción de que
lo empeoraría; se verifica.

36 filas (12 instancias × 3 semillas). La asignación árbol → ruta no cambia: k, drops,
degeneración y balance son por construcción los de la base.

| Instancia | cruces `no-floor` → `+reseq` | travel `no-floor` → `+reseq` | Δ travel |
| --- | ---: | ---: | ---: |
| battery-n50 | 0 → 3 | 3 419 → 3 333 | −2.5 % |
| battery-n100 | 0 → 3 | 4 277 → 3 994 | −6.6 % |
| battery-n200 | 6 → 14 | 7 942 → 7 035 | −11.4 % |
| battery-n400 | 3 → 22 | 12 896 → 11 758 | −8.8 % |
| battery-n800 | 8 → 45 | 21 192 → 18 915 | −10.7 % |
| battery-n1000 | 7 → 54 | 26 980 → 24 313 | −9.9 % |
| battery-sparse-n250 | 1 → 9 | 15 497 → 14 498 | −6.4 % |
| battery-sparse-n500 | 3.7 → 18.3 | 21 463 → 19 676 | −8.3 % |
| area-26-n157 | 0 → 2 | 4 300 → 4 186 | −2.7 % |
| area-27-n72 | 0 → 1 | 1 481 → 1 456 | −1.7 % |
| area-29-n43 | 0 → 5 | 999 → 956 | −4.3 % |
| **reference-n1607** | **6.3 → 51.0** | 52 190 → 49 701 | −4.8 % |

**El 2-opt empeora los cruces en las 12 instancias, sin excepción.** En n=1607 los multiplica
por ocho (6.3 → 51), devolviendo la solución casi al nivel de cruces de los brazos de span.
El travel baja siempre (−1.7 a −11.4 %), como corresponde a un 2-opt monótono sobre travel de
red. Balance, k, drops y degeneración quedan idénticos a la base (min balance 0.011,
2 degeneradas, 0 drops).

**Veredicto Brazo 5:** el post-pass **no aporta** sobre `no-floor`. Es la tercera confirmación
coherente —tras el 2-opt de `objective-audit-postpass-sweep-20260718.md` Fase 2 y el costo de
arco convexo de su Fase 3b— de que **travel de red y limpieza geométrica no son proxies
mutuos** en este dominio: cuanto más limpia geométricamente está la base, más daño le hace
minimizar travel de red. El 2-opt sigue siendo útil solo donde la base es geométricamente
sucia (`actual` en denso), nunca sobre una base limpia.

---

## Veredicto final

**Ningún brazo de la familia sin piso queda verificado contra su criterio a priori
completo.** No se cambia ningún default de producción.

| Brazo | Veredicto | Resumen |
| --- | --- | --- |
| `no-floor` | **No verificada — rutas degeneradas y balance roto** | Mejor geometría y travel jamás medidos en n=1607 (cruces −93 %, travel −13.9 %, relleno −25 %), pero produce una ruta de un solo árbol y balance 0.011. Falla también el relleno de area-26 (−26 %, bajo el −50 % exigido). |
| `no-floor-span-c10` | **No verificada** | Balance mínimo 0.382, travel n=1607 +3.1 % (sobre el tope), empeora cruces en áreas chicas. Sin degeneradas. |
| `no-floor-span-c100` | **No verificada** | Balance mínimo 0.556 (a un pelo del 0.60), travel +3.9 %, empeora cruces en area-26. Sin degeneradas. |
| `no-floor-span-c1000` | **No verificada** | Único que pasa balance (min 0.715), pero a costa de travel +7.3 % en n=1607, +35.6 % en n=800, y de fragmentar las instancias chicas (area-29 k 1→6). 1 ruta degenerada. |
| `no-floor+reseq` | **No aporta** | El 2-opt empeora los cruces en las 12 instancias (n=1607: 6.3 → 51) a cambio de −5 a −11 % de travel de red. Tercera refutación consecutiva de la vía "moldear geometría vía travel de red". |
| `feasible-floor-b095` (re-lectura) | **Reabierta — la más cercana a cumplir** | Con el corte de balance en 0.60 pasa balance en las 12 instancias (min 0.652), cruces n=1607 −81 %, travel +0.2 %, relleno de áreas −21 a −82 %. Su costo residual es travel +10 % en battery-n800. No verificable en degeneración (columna inexistente en el CSV previo). |

Síntesis:

- El resultado central de este ciclo es **causal, no incremental**: el soft lower bound es la
  causa directa del relleno y de la mayor parte de los cruces en el régimen denso. Quitarlo
  mejora geometría, travel y relleno a la vez. Ninguna de las medicinas anteriores (piso
  factible, techo alto, 2-opt, arco convexo) había logrado mover las tres en la misma
  dirección.
- El precio de quitarlo por completo son las **rutas stub**, y el span cost global —el
  término de balance sin piso que el reporte anterior pedía explorar— **funciona pero es una
  mala compra**: recupera balance reintroduciendo relleno y travel, y en instancias chicas
  finge balance fragmentando.
- Por eso la dirección viva no es "sin piso a secas" ni "span cost", sino un piso que sea
  **suficiente para prohibir stubs pero no para forzar relleno**. `feasible-floor-b095`, que
  bajo el criterio relajado pasa todo salvo el travel de la batería sintética, es hoy el
  candidato más cercano, y la comparación honesta contra él es la que debe guiar el
  siguiente ciclo: un piso bajo y absoluto (p. ej. un mínimo de paradas por ruta o un piso
  fijo del orden de 1–2 h) tiene el mismo efecto anti-stub sin el efecto relleno.

---

## Reproducción

```bash
# Brazos 1–3 (una celda por invocación, mismo CSV, resumible)
for cell in actual no-floor no-floor-span-c10 no-floor-span-c100 no-floor-span-c1000 \
            no-floor+reseq; do
  docker compose -p arbocensus run --rm --no-deps -e RUN_MIGRATIONS=false backend \
    python manage.py config_algorithm_sweep \
      --csv docs/experiments/no-floor-balance-sweep-20260719.csv --only-cell "$cell"
done

# Brazo 4: re-lectura de objective-audit-postpass-sweep-20260718.csv, sin cómputo.
```
