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

_(pendiente — se agrega tras medir, sin tocar el criterio de arriba)_
