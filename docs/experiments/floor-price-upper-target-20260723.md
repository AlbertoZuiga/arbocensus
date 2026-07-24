# Precio del piso de duración × target del soft upper (factorial 2×4×2)

**Fecha:** 2026-07-23
**Estado al commitear esta sección:** pre-registro. Motivación, diseño, celdas, instancias,
métricas, predicciones y criterio se commitean **antes** de medir nada. Los resultados se
agregan después, sin tocar el criterio.

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: los defaults (`PenaltyConfig` actual — `soft_lower_penalty`
10 000, `soft_upper_target` midpoint) quedan intactos. Lo nuevo es opt-in.

---

## 1. Motivación

El objetivo del VRP tiene dos parámetros del canal de duración que la serie nunca barrió como
factores independientes:

- **El precio del piso blando `soft_lower_penalty`.** Con el default 10 000 contra un arco de
  1/s, el piso de `T_min` (7 200 s) es una restricción dura disfrazada de precio: por debajo de
  `T_min` el solver está *pagado* a −9 999/s por caminar en círculos
  (`.claude/rules/ortools-vrp.md`, "Marginal price, not nominal weight"). Toda la familia de
  pisos que la serie exploró — `feasible-floor-b*`, `service-floor`, `no-floor`,
  `no-floor-lowfloor*` — movió el **target** del piso (dónde está) o lo quitó del todo, pero
  **nunca movió su precio** dejando el target en `T_min`. Bajar el precio sin quitar el piso es
  un punto no medido: relaja el subsidio al relleno sin abandonar la contención de flota.

- **El target del soft upper con el piso default.** El arm `upper-tmax-tmin9000` corrió el upper
  a `T_max`, pero **acopló** ese cambio a un piso de 9 000 s (`TIGHT_TMIN_SEC`). Nunca se corrió
  el upper@`T_max` **manteniendo el piso default de 7 200 s**. Ese es el factor B limpio: mover
  solo el techo blando, sin tocar el piso.

El cruce de ambos es un factorial 2 factores que llena un hueco declarado del espacio de diseño.

### Reserva heredada sobre la métrica de cruces

El ciclo previo (`docs/experiments/crossing-metric-validation-20260723.md`) estableció que
`crossings_chord` (auto-cruces sobre cuerdas rectas) es un **proxy parcial** de la geometría real
(ρ = 0,527) y que **en `n=1607` invierte el orden** (ρ = −0,575). El criterio histórico de la
serie se lee sobre `crossings_chord`; este ciclo lo mantiene por continuidad **pero reporta
`crossings_road` junto a él en toda tabla**, y para `n=1607` comenta explícitamente la reserva
sobre el nivel absoluto de cualquier lectura de cruces.

## 2. Diseño

**Factor A — precio del piso `soft_lower_penalty` ∈ {10 000 (control), 2 000, 500, 100}.**
**Factor B — target del soft upper ∈ {midpoint (control), tmax}.**

Ambos factores sobre el arm `actual` (`BALANCE_ARM_ACTUAL`), que da
`lower = (T_min = 7 200, soft_lower_penalty)` y `upper = (target, 500)`. Con `soft_upper_target =
tmax` el techo es `T_max = 10 800` **con el piso default de 7 200** — la combinación limpia que
nunca se corrió. **No** se usa `upper-tmax-tmin9000`: ese arm confunde el target con un piso de
9 000.

**8 celdas** (label → configuración):

| label | soft_lower_penalty | soft_upper_target | banda upper (s) |
| --- | ---: | --- | ---: |
| `floor10000-mid` **(control = `actual`)** | 10 000 | midpoint | 9 000 |
| `floor10000-tmax` | 10 000 | tmax | 10 800 |
| `floor2000-mid` | 2 000 | midpoint | 9 000 |
| `floor2000-tmax` | 2 000 | tmax | 10 800 |
| `floor500-mid` | 500 | midpoint | 9 000 |
| `floor500-tmax` | 500 | tmax | 10 800 |
| `floor100-mid` | 100 | midpoint | 9 000 |
| `floor100-tmax` | 100 | tmax | 10 800 |

**Instancias.** Las 12 congeladas de `docs/experiments/instances/` (`battery-n{50,100,200,400,
800,1000}`, `battery-sparse-n{250,500}`, `area-{26-n157,27-n72,29-n43}`, `reference-n1607`).

**Semillas.** 3 réplicas reales (permutación del orden de nodos; OR-Tools no expone RNG). La
`σ` entre réplicas debe ser > 0 en las celdas no deterministas; si es 0,0 al segundo, las
semillas no llegaron al solver y el cómputo son copias.

**Línea base RE-CORRIDA dentro del ciclo.** La celda `floor10000-mid` ES `actual`; se compara
contra ella, **no** contra medias publicadas por reportes viejos (la varianza entre corridas
supera la varianza entre semillas de una misma corrida).

**Presupuesto.** `default_time_limit_sec` de producción: 120 s por resolución en las instancias
grandes. 8 celdas × 12 instancias × 3 semillas = 288 resoluciones (menos las celdas `k=1`
deterministas, que colapsan a 1 semilla útil).

## 3. Predicciones registradas ANTES de medir

- **P1 (cordura por construcción).** `floor10000-mid` reproduce `actual` dentro de la `σ` entre
  semillas: mismo `k`, `travel` y `balance` en cada instancia. Si NO coincide, el cableado del
  factorial está mal y no hay nada que interpretar.
- **P2 (rampa monótona por construcción).** A `soft_upper_target = midpoint` fijo, al **bajar**
  `soft_lower_penalty` (10 000 → 100) el objetivo degenera hacia `service-floor` (piso sin
  precio): el subsidio al relleno bajo `T_min` se debilita, así que **`relleno_msf` no aumenta**
  (baja en áreas holgadas) pero la contención de flota se afloja, así que **`k` no disminuye**
  (sube donde el piso era lo único que fusionaba rutas cortas). En `floor100-*` se espera el
  comportamiento más cercano a `no-floor`/`service-floor` ya medidos. Una rampa **no monótona**
  en `k` o `relleno_msf` a lo largo de A señala ruido, no señal.
- **P3.** A `soft_lower_penalty` fijo, `soft_upper_target = tmax` produce rutas más llenas: **`k`
  ≤** el de la celda `midpoint` correspondiente, porque el techo a `T_max` deja crecer cada ruta
  hasta la capacidad dura antes de cobrar el +501.
- **P4 (cruces en `n=1607`).** Herencia del gancho de ciclos previos ("el soft upper en `T_max`
  desarma cruces", F13/Q1b, medido sobre cuerdas): en `n=1607` las celdas `*-tmax` bajan
  `crossings_chord` frente a `floor10000-mid`. **Reserva pre-registrada:** por el ciclo previo,
  `crossings_road` en `n=1607` puede **no** acompañar ese movimiento (o invertirlo); ambas
  columnas se reportan y el veredicto geométrico de `n=1607` se lee con esa reserva explícita.

## 4. Criterio de aceptación a priori (heredado, no renegociable)

Una celda "gana" solo si cumple **todo**, comparada contra `floor10000-mid` RE-CORRIDA:

1. `n=1607`: `crossings_chord` **−≥ 30 %**.
2. `n=1607`: `travel` **≤ +3 %**.
3. `n=1607`: `k` **≤ 26**.
4. Áreas (`area-26/27/29`): `relleno_msf` **−≥ 30 %**.
5. Áreas: `crossings_chord` **sin empeorar**.
6. Todas las instancias: **0 drops**.
7. Todas: `balance` **≥ 0,60**.
8. Todas: **0 rutas degeneradas** (`< 5` paradas **o** `< 1 800` s).

Un brazo que mejora una métrica y empeora otra **no** es ganadora parcial: **falla el criterio**,
y se dice así. La métrica de cruces del criterio se lee sobre `crossings_chord` por continuidad
histórica; se acompaña de `crossings_road` con la reserva del §1 para `n=1607`.

## 5. Qué salidas son publicables

**Las tres salidas son publicables.** Si ninguna celda cumple el criterio completo, **ningún
default de producción cambia**: el hallazgo se publica como propuesta verificada + trabajo
futuro. Un resultado negativo — "bajar el precio del piso o subir el techo no compra geometría
sin romper balance/flota" — es tan citable como el positivo. El ciclo NO está diseñado para
elegir la mejor celda a posteriori.

## 6. Lo que NO hace este ciclo

- No cambia ningún default de producción ni propone uno salvo que una celda cumpla el criterio
  completo.
- No re-abre la familia de pisos ya refutada (`feasible-floor-*`, `stops`, `no-floor`): esos
  movieron el **target** del piso; este mueve su **precio** y el target del **techo**, ejes
  ortogonales.
- No adopta `crossings_road` como criterio (eso es un ciclo posterior con su propio
  pre-registro); solo lo reporta como contexto.
- No toca el post-pass 2-opt, los clusters, el warm start ni los coeficientes de span.

## 7. Costos y riesgos

- **CPU.** Re-resolver 8 × 12 × 3 con presupuesto de producción; barrido de varias horas.
- **`crossings_road` es O(m²)** y exige llamadas OSRM `fetch_route_path` por ruta; ya acotado y
  paralelizado por el driver.
- **Infra compartida.** El volumen Postgres es externo; nunca `docker compose down -v`. Un solo
  stack pesado a la vez; revisar que ningún otro worktree esté midiendo antes de levantar.

---

## Resultados

Datos: `floor-price-upper-target-20260723.csv` (**288 filas** = 8 celdas × 12 instancias ×
3 semillas) y su `.sequences.jsonl`. Un solo barrido secuencial, mismo presupuesto de
producción (120 s) para las 8 celdas. `wall_clock` no juzga nada. Toda `σ` reportada es la
desviación **poblacional** sobre las 3 semillas del grupo.

### Comprobaciones del instrumento (antes de leer nada más)

- **P1 (cordura) — pasa.** `floor10000-mid` en `n=1607` da chord 64,7 ± 9,0, road 41,0 ± 5,1,
  `k` = 25, balance 0,849 — dentro de la varianza del `actual` publicado por el ciclo previo
  (chord 65,3 ± 7,0, road 43,0 ± 4,0). El cableado del factorial reproduce la línea base.
- **Semillas reales — pasa.** 90 grupos `(celda, instancia)` tienen σ > 0 entre sus tres
  semillas; **0 grupos** tienen σ = 0 fuera de los casos `k = 1` deterministas por construcción.
  Las permutaciones de nodos llegaron al solver.

### Factor A — precio del piso `soft_lower_penalty` (a target midpoint fijo)

| celda | k | travel | Δtravel | balance | chord | road | deg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `floor10000-mid` **(control)** | 25,0 | 59 946 | +0,0 % | 0,849 | 64,7 ± 9,0 | 41,0 | 0,0 |
| `floor2000-mid` | 25,0 | 59 941 | −0,0 % | 0,849 | 64,7 ± 9,0 | 41,0 | 0,0 |
| `floor500-mid` | 25,0 | 59 729 | −0,4 % | 0,848 | 66,7 ± 9,7 | 41,7 | 0,0 |
| `floor100-mid` | 25,7 | 62 596 | **+4,4 %** | 0,833 | 69,0 ± 1,4 | 45,0 | 0,3 |

(valores de `n=1607`; medias de 3 semillas). El precio del piso es **inerte entre 10 000 y 500**:
`floor2000-mid` reproduce el control al segundo en 2 de sus 3 semillas de `n=1607` (travel 59 941
vs 59 946) y `floor500-mid` queda a −0,4 % de travel y +2,0 cuerdas, muy dentro de la σ entre
semillas del control (±9,0 en chord). *Inerte* significa **sin efecto sistemático**, no
bit-a-bit: sobre las 12 instancias, 53/216 comparaciones celda-semilla de `floor2000-mid` y
74/216 de `floor500-mid` difieren del control en algún dígito — el precio perturba la trayectoria
de GLS y hace caer la búsqueda en otro óptimo local del mismo nivel, sin mover ninguna métrica en
una dirección. Es la predicción del marco de precios
marginales — un piso a 500/s todavía supera con creces la presión del arco (1/s), así que sigue
siendo una **restricción dura disfrazada de precio**. Solo a **100** el relleno bajo `T_min` se
afloja lo suficiente para mover algo, y lo que mueve es **malo**: travel +4,4 % (supera el techo
+3 % del criterio), balance cae hasta **0,577** en su peor instancia (bajo el piso 0,60 del
criterio), `k` sube. Bajar el precio del piso no compra geometría; erosiona la contención de
flota y el balance. **P2 (rampa) confirmada en dirección**: al abaratar el piso, `relleno_msf` no
sube y `k` no baja; el único punto que se mueve (100) degrada.

### Factor B — target del soft upper a `T_max` (con el piso default 7 200)

| celda | k | travel | Δtravel | balance | chord | Δchord | road | Δroad | deg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `floor10000-mid` **(control)** | 25,0 | 59 946 | +0,0 % | 0,849 | 64,7 ± 9,0 | +0 % | 41,0 ± 5,1 | +0 % | 0,0 |
| `floor10000-tmax` | 25,0 | 58 363 | −2,6 % | 0,723 | 4,3 ± 0,5 | **−93 %** | 58,3 ± 10,3 | **+42 %** | 0,7 |
| `floor2000-tmax` | 25,0 | 58 356 | −2,7 % | 0,723 | 4,3 ± 0,5 | −93 % | 58,3 ± 10,3 | +42 % | 0,7 |
| `floor500-tmax` | 25,0 | 58 356 | −2,7 % | 0,723 | 4,3 ± 0,5 | −93 % | 58,3 ± 10,3 | +42 % | 0,7 |
| `floor100-tmax` | 25,0 | 58 466 | −2,5 % | 0,707 | 4,3 ± 0,5 | −93 % | 59,3 ± 10,9 | +45 % | 0,7 |

(valores de `n=1607`). Mover el techo a `T_max` **colapsa `crossings_chord` un 93 %** (64,7 → 4,3)
a cualquier precio del piso, con travel **−2,6 %** y `k` = 25 sin drops. Leída solo sobre cuerdas,
parece la ganadora rotunda del criterio (chord −≥30 %, travel ≤+3 %, k≤26). **No lo es**, y la
reserva pre-registrada del §1 dice exactamente por qué:

- **`crossings_road` en `n=1607` SUBE +42 %** (41,0 → 58,3). La métrica validada — la que ordena
  como el solver optimiza y el censista camina — dice que la geometría **empeora**.
- **La Spearman chord~road sobre `n=1607` es −0,618** (global 0,520). El −93 % de chord es
  literalmente el **artefacto de inversión** que el ciclo previo dejó pre-registrado. Este ciclo
  lo **replica de forma independiente** sobre 8 configuraciones nuevas (ρ global 0,520 vs 0,527
  del ciclo previo; `n=1607` −0,618 vs −0,575).
- **balance** cae 0,849 → 0,723 y aparece una **ruta degenerada** en 2 de 3 semillas (< 5 paradas;
  `dur_min` = 7 578 s, así que es un stub de pocas paradas muy dispersas, no una ruta corta).

### Áreas — `relleno_msf` y cruces (medias de 3 semillas)

| celda | area-26 relleno | area-27 relleno | area-29 relleno | area-26 chord | area-27 chord | area-29 chord |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `floor10000-mid` **(control)** | 1 440 | 4 821 | 1 242 | 0,3 | 6,7 | 6,0 |
| `floor10000-tmax` | 1 081 (**−25 %**) | 1 727 (−64 %) | 1 234 (**−0,6 %**) | 1,0 (**+200 %**) | 2,7 (−60 %) | 6,3 (**+6 %**) |
| `floor*-tmax` (2000/500/100) | 1 081–1 225 (−15…−25 %) | 178–199 (**−96 %**) | 1 234–1 238 (−0,6 %) | 0,7–1,0 (peor) | 0,0 (−100 %) | 2,0 (−67 %) |
| `floor*-mid` (2000/500/100) | ≈ control | ≈ control | ≈ control | ≈ control | 4,7–8,3 | 3,0–4,7 |

**La diferencia entre `floor10000-tmax` (−64 %) y los pisos baratos (−96 %) en `area-27` no es un
efecto del precio.** Es una sola semilla: `floor10000-tmax` seed 1 aterriza en `k = 2`
(relleno 4 824) mientras sus otras dos semillas y todas las de los pisos baratos dan `k = 1`
(relleno 178–199). Con `n = 72` la media de 3 semillas es frágil ante ese salto de `k`; leer ahí
una interacción precio×target sería leer ruido. El resto de las áreas no distingue precios.

Las áreas revelan que `T_max` es **regime-dependent**: en `area-27` (holgada) el relleno cae hasta
**−96 %** y los cruces desaparecen, pero en **`area-26` el relleno solo baja −25 %** (bajo el
−30 % del criterio) **y sus cuerdas empeoran +200 %**, y en **`area-29` el relleno no se mueve**
(−0,6 %) mientras sus cuerdas empeoran en el brazo `10000-tmax` (+6 %). No hay un único default que
sirva a las tres áreas.

### Autocruces sobre calles — agregado de las 12 instancias

El criterio geométrico solo mira `n=1607` y las áreas. Sumando `crossings_road` (autocruces
**dentro de cada ruta**, sobre la traza OSRM) de las 12 instancias, **ninguna celda mejora al
control**:

| celda | Σ road (12 instancias) | Δ | instancias mejor / peor |
| --- | ---: | ---: | ---: |
| `floor10000-mid` **(control)** | 190 | +0 % | — |
| `floor2000-mid` | 198 | +4 % | 1 / 3 |
| `floor500-mid` | 202 | +6 % | 2 / 5 |
| `floor100-mid` | 242 | +27 % | 0 / 10 |
| `floor10000-tmax` | 286 | **+51 %** | 5 / 7 |
| `floor2000-tmax` | 288 | +51 % | 4 / 8 |
| `floor500-tmax` | 280 | +48 % | 4 / 8 |
| `floor100-tmax` | 293 | **+54 %** | 3 / 9 |

Los brazos `*-tmax` ganan cruces en instancias chicas u holgadas (`area-27` 12,7 → 2,3;
`battery-n50` 3,3 → 1,0) y los pierden con creces en las densas (`battery-n800` 22,0 → 56,7;
`battery-n1000` 47,0 → 72,3; `battery-n400` 17,7 → 30,7; `n=1607` 41,0 → 58,3). Sobre la métrica
validada, **ninguna configuración de este factorial reduce los autocruces intra-ruta**; el −93 %
de cuerdas es de signo contrario al agregado de calles.

### Balance, degeneración y drops — global (12 instancias)

| celda | min balance | max rutas degeneradas | total drops |
| --- | ---: | ---: | ---: |
| `floor10000-mid` / `floor2000-mid` / `floor500-mid` | 0,837–0,839 | 0 | 0 |
| `floor100-mid` | **0,577** | 0,3 | 0 |
| `floor{10000,2000,500,100}-tmax` | 0,707–0,709 | **0,7** | 0 |

### Cuadro de predicciones

| # | predicción | resultado | veredicto |
| --- | --- | --- | --- |
| P1 | `floor10000-mid` ≈ `actual` (cordura) | chord/road/k/balance dentro de varianza | **acertada** |
| P2 | abaratar el piso: `relleno_msf` no sube, `k` no baja; rampa monótona | inerte hasta 500, degrada a 100 (balance 0,577, travel +4,4 %) | **acertada** |
| P3 | `*-tmax`: `k` ≤ el de `*-mid` | `k` = 25 en ambos (igual, no menor; `n=1607` saturada) | **acertada (débil)** |
| P4 | `*-tmax` baja `crossings_chord` en `n=1607`; reserva: `road` puede no acompañar | chord −93 %, pero **road +42 %** e inversión ρ −0,618 | **chord acertada, refutada por la reserva** |

---

## Veredicto

**Ninguna de las 8 celdas cumple el criterio de aceptación completo. Ningún default de producción
cambia.**

Se aplica el criterio a priori **sin renegociarlo**, celda por celda:

- **`floor{2000,500}-mid`** — indistinguibles del control dentro de la σ entre semillas. Fallan el
  criterio 1 (chord de `n=1607` +0…+3 %, lejos del −30 %), el 4 (relleno de las áreas ≈ control) y
  el 5 (`floor2000-mid` empeora las cuerdas de `area-27` 6,7 → 7,3; `floor500-mid` las de
  `area-26` 0,3 → 0,7). El piso es una restricción dura hasta un precio ≈ 500; abaratarlo ahí no
  hace nada: **no gana**.
- **`floor100-mid`** — falla el criterio 2 (travel +4,4 % > +3 %), el 7 (balance 0,577 < 0,60) y
  el 8 (ruta degenerada en 1 de 3 semillas de `n=1607`), además del 1, el 4 y el 5.
  Abaratar el piso hasta que muerda **rompe** balance y travel sin comprar geometría: **no gana**.
- **`floor{10000,2000,500,100}-tmax`** — su único triunfo aparente es `crossings_chord` −93 %,
  y ese triunfo lo **refuta la reserva pre-registrada**: sobre `crossings_road` (la métrica
  validada) los cruces de `n=1607` **suben +42 %**, con ρ chord~road = −0,618 confirmando que el
  −93 % es el artefacto de inversión, y en el agregado de las 12 instancias `road` sube +48…+54 %.
  Además fallan el criterio 4 (área-26 relleno −25 %, área-29
  −0,6 %; ambos sobre el −30 %), el 5 (área-26 chord +200 %, área-29 chord peor) y el 8 (ruta
  degenerada en 2/3 semillas de `n=1607`). Un brazo que baja las cuerdas y **sube las calles** no
  es ganadora parcial: **falla el criterio**.

**Resultado negativo, publicado como estaba pre-registrado.** No se propone ningún cambio de
default.

### Lo que queda establecido

1. **El precio del piso de duración no es una palanca.** Entre 10 000 y 500 es inerte (piso duro);
   a 100 empieza a morder y lo que produce es peor balance y más travel, no mejor geometría. Queda
   **descartado** barrer el precio del piso como vía para relajar el relleno: hay que quitar el
   piso o mover su target (ejes ya refutados en la familia `feasible-floor`/`no-floor`), no
   abaratarlo.
2. **El upper@`T_max` con el piso default es regime-dependent y su ganancia en `n=1607` es un
   artefacto de cuerdas.** Ayuda a un área holgada (`area-27`) pero rompe otras (`area-26`,
   `area-29`) y, en la instancia densa, su −93 % de cuerdas es +42 % de calles; sobre las 12
   instancias el agregado de autocruces sobre calles sube +48…+54 %. Queda **descartado**
   como default global. Confirma el hallazgo previo de "guardia por régimen, no un único config".
3. **Replicación independiente del ciclo de la métrica de cruces.** Sobre 8 configuraciones
   nuevas, la divergencia chord/road se reproduce (ρ global 0,520 ≈ 0,527; `n=1607` −0,618 ≈
   −0,575). El criterio geométrico de la serie leído sobre cuerdas en `n=1607` está midiendo el
   signo equivocado; este ciclo lo confirma con datos nuevos, no reciclados.

### Lo que este ciclo deja abierto

Adoptar `crossings_road` como criterio geométrico de referencia — ya propuesto por el ciclo previo
— gana aquí una **segunda confirmación independiente**. Su adopción formal, y la re-lectura de los
veredictos juzgados sobre cuerdas, sigue correspondiendo a un ciclo con su propio pre-registro.
Un `T_max` **condicionado al régimen del área** (holgada vs densa) queda como hipótesis no
probada: este factorial midió un target global, no uno por régimen. Las secuencias quedan
persistidas (`.sequences.jsonl`), así que ese re-juicio no exige re-resolver.
