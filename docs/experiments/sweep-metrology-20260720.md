# Metrología del barrido y re-veredicto de la serie

**Fecha:** 2026-07-20
**Estado:** pre-registro (este documento se commitea **antes** de correr nada).

Todo corre por *overrides* de CLI del driver `config_algorithm_sweep`. La configuración de
producción del solver no cambia: defaults (`spatial_term`, `PenaltyConfig` actual, coeficiente
de span espacial 3) intactos. Lo nuevo es opt-in.

Este ciclo no agrega ningún brazo. Arregla dos defectos del **instrumento** que alcanzan a los
cinco barridos de la serie, y vuelve a juzgar lo ya medido con el instrumento arreglado.

---

## Por qué este ciclo

El ciclo anterior (`combined-floor-sweep-20260720.md`) dejó dos hallazgos transversales:

1. **Las "3 semillas" nunca fueron réplicas.** El driver escribía `seed` en la fila del CSV y en
   la clave de reanudación, pero nunca lo pasaba al solver. Medido en ese ciclo: 10 celdas × 3
   semillas → un único resultado distinto. Ninguna cifra publicada es incorrecta, pero **ninguna
   tiene barras de error**, y cada barrido costó 3× el cómputo.
2. **La métrica `relleno_sec` tiene su cero en una cota inalcanzable.** Define
   `relleno := travel_total − (n − k)·nn̄`, donde `nn̄` es la media de la distancia al vecino más
   cercano. Ningún recorrido real llega a esa cota: asignar a cada nodo su arista más barata
   viola la restricción de grado 2 de un camino. La métrica cuenta **geometría irreducible como
   si fuera relleno**.

Y el resultado que vuelve decisivo arreglarlos: en `area-26-n157` el piso de duración es una
restricción **inactiva**. La Parte A del ciclo anterior demostró que `k = 3` es el mínimo
factible bajo `T_max` con cobertura completa, que la geometría obliga `travel ≥ 3 618 s` y que
el piso sólo obliga `2 760 s`. `feasible-floor-b095` pasa **todos** los criterios de la serie
salvo el relleno de esa instancia — y ese relleno resultó ser geometría irreducible medida con
una regla mal calibrada.

**Pregunta del ciclo:** ¿la ganadora ya estaba sobre la mesa? ¿Cumple `feasible-floor-b095` el
criterio completo cuando se lo juzga con una métrica de relleno **alcanzable** y con réplicas
**de verdad**?

---

## Fase 0 — el instrumento (ya implementado, commit previo a este)

### Semillas reales: qué mecanismo quedó y por qué

Se verificó primero si OR-Tools expone un RNG. Inspeccionados dentro del contenedor los dos
protos, `pywrapcp.DefaultRoutingSearchParameters()` y `pywrapcp.DefaultRoutingModelParameters()`
(este último incluye `solver_parameters`): **ninguno tiene campo de semilla**. No hay
`random_seed`, `seed` ni equivalente en ninguno de los tres descriptores.

Mecanismo adoptado, en consecuencia: **permutación del orden de los nodos** según la semilla,
antes de construir el modelo. La permutación cambia el desempate de `PATH_CHEAPEST_ARC` (que
recorre los arcos en orden de índice) y con ello la solución inicial y toda la trayectoria de
GLS. Se revierte al extraer la solución, de modo que las rutas devueltas están en índices
originales.

Dos propiedades que importan:

- **La semilla 0 es la permutación identidad.** Producción nunca pasa `node_seed`, así que el
  comportamiento de producción es idéntico bit a bit al de antes de este ciclo.
- **Mide la varianza del pipeline entero**, no la de un sorteo interno del solver. Es la
  magnitud que interesa: cuánto se mueve el resultado publicable ante una perturbación
  irrelevante del input.

### Métrica nueva `relleno_msf_sec`

```
relleno_msf := travel_total − MSF_k
```

`MSF_k` = bosque generador mínimo de `k` componentes sobre la matriz simetrizada
`min(d_ij, d_ji)` (= MST menos sus `k − 1` aristas más pesadas). `k` caminos abiertos que cubren
`n` nodos **son** un bosque generador de `k` componentes, así que `travel_total ≥ MSF_k` es una
cota válida; simetrizar hacia abajo sólo puede subestimar el costo dirigido, lo que mantiene la
validez. El cálculo ya existía en `instance_decomposition` y se extrajo a un módulo compartido
(`apps/optimization/bounds.py`) en vez de duplicarse.

La columna se **agrega junto a** `relleno_sec`, nunca en reemplazo: la vieja preserva la
comparabilidad con los cinco CSV previos, la nueva es la que juzga. El CSV también guarda
`msf_k_sec`, para que la aritmética sea verificable fila a fila.

La cota deja de valer si la solución abandona nodos, así que `relleno_msf_sec` queda vacío
cuando `drops > 0`, y el driver **aborta** si observa `travel_total < MSF_k` (un error de
contabilidad o de la cota, no un resultado).

---

## Fase 1 — criterio

### Lo que NO se toca (heredado, no renegociable a posteriori)

- **n=1607:** cruces **−≥30 %** vs `actual`, travel **≤+3 %**, k **≤26**.
- **Áreas chicas (157/72/43):** cruces **sin empeorar**.
- **Global:** **0 drops**; **balance min/max ≥0.60** en **toda** instancia; **0 rutas
  degeneradas**, con la definición absoluta de siempre (**<5 paradas** O **<1 800 s**).

### Lo único que se reescribe: el criterio de relleno de áreas

**Antes:** `relleno_sec` **−≥50 %** vs `actual`.
**Ahora:** `relleno_msf_sec` **−≥30 %** vs `actual`.

**Justificación aritmética, anterior al resultado.** La demostración de que el cero viejo es
inalcanzable está en `combined-floor-sweep-20260720.md` (secciones A.1 y A.4), escrita el ciclo
pasado y **antes** de este re-juicio. Sobre `area-26-n157`, con los números publicados ahí:

- Cero viejo: `(n − k)·nn̄ = (157 − 3)·15.47 = 2 383 s`.
- Cota geométrica real: `MSF_3 = 3 618 s`.
- Diferencia: **1 235 s**, contra un `relleno_sec` de `actual` de **2 579 s**.

Es decir: **el 48 % de lo que la métrica vieja llamaba "relleno" en esa instancia es geometría
que ningún recorrido puede evitar.** Pedir −50 % sobre esa base era pedir que el brazo eliminara
todo el relleno real *y además* una parte de la geometría. El criterio no era exigente: era
insatisfacible por construcción.

**Por qué −30 % y no otro número.** `MSF_k` es una relajación: ignora la restricción de grado 2,
así que el óptimo real de ruteo está por encima de ella. Para instancias euclídeas la brecha
conocida entre un recorrido óptimo y el MST es del orden de **10–30 %** del MST. Con un cero que
el óptimo mismo no toca, exigir −100 % del exceso sería otra vez imposible; **−30 % del exceso
de `actual` sobre `MSF_k`** pide que el brazo cierre alrededor de un tercio de la distancia a una
cota que ya se sabe optimista por esa misma magnitud. El número se fija por ese argumento, no por
inspección de resultados, y se commitea antes de medir.

**Sensibilidad declarada por adelantado.** Como el umbral es un juicio y no un hecho, el reporte
publicará el **valor medido** de `relleno_msf` en cada instancia y cada brazo, y dirá
explícitamente a partir de qué umbral cambiaría el veredicto. Cualquiera puede rehacer el juicio
con otro umbral, o con la regla antigua: `relleno_sec` sigue en el CSV.

### Regla de varianza (nueva, y aplica a todo el ciclo)

Con réplicas reales, una diferencia entre brazos cuenta como **real** sólo si

```
|media_A − media_B| > desv_A + desv_B
```

sobre las 5 semillas. Si no la supera, se reporta como **empate**, explícitamente y con esa
palabra. Los criterios se evalúan sobre la **media** de las 5 semillas; el balance mínimo de la
suite se reporta también como peor semilla, porque un piso de cordura que sólo se cumple en
promedio no es un piso.

---

## Fase 2 — lo que se va a medir

### 2a. Re-juicio retroactivo (sin solver)

`MSF_k` depende sólo de la instancia y de `k`, ambos presentes en las filas ya publicadas, así
que los cinco CSV previos se re-juzgan sin volver a resolver nada: se computa la tabla `MSF_k`
de las 12 instancias con `instance_decomposition` y se une con `rejudge_relleno`. Pregunta a
responder **con números**: ¿cuántos "fallos" de relleno de la serie eran artefactos de la regla?

### 2b. Head-to-head con réplicas reales

**5 semillas**, 12 instancias congeladas, estrategia `spatial_term`, cuatro brazos:

| Brazo | Papel |
| --- | --- |
| `actual` | Control (producción). |
| `feasible-floor-b095` | Candidato de la serie. |
| `no-floor-stops10` | Mejor geometría sin piso de duración. |
| `feasible-floor-b060-stops10` | Mejor travel/relleno de la serie, falla balance. |

Es la primera cifra con barras de error de toda la serie. Media ± desviación en todas las
métricas de criterio.

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

**Nota de ejecución.** Las celdas se corren en flujos paralelos sobre la misma máquina. El
límite de tiempo del solver es de reloj, así que la contención de CPU reduce iteraciones de GLS:
`wall_clock_sec` y `t_metaheuristic_sec` no son comparables con barridos previos. Los cuatro
brazos se corren bajo el mismo esquema y con el mismo grado de paralelismo, así que la
comparación entre ellos sí es válida. Esta contención es parte de lo que las barras de error
van a medir.

---

## Veredicto que este ciclo se compromete a emitir

- Si `feasible-floor-b095` pasa el criterio **completo** bajo la métrica corregida y con
  varianza, es la **primera ganadora verificada de la serie**, y se dice con esas palabras. La
  decisión de adopción queda planteada, no ejecutada: **no se cambia ningún default**.
- Si no pasa, se cierra la familia de pisos con veredicto limpio y se afirma que la palanca
  queda **fuera del objetivo del VRP** (`T_max`, tiempo de servicio, partición territorial), que
  es lo único que mueve el `k` que la aritmética impone.

## Riesgo declarado

Reescribir una métrica después de cinco fallos **se parece a mover la portería**. Mitigación,
que queda escrita aquí y no se puede añadir después:

1. La justificación es **aritmética y anterior al resultado**: la demostración de que el cero
   viejo es inalcanzable está publicada en el reporte del ciclo pasado, escrita antes de este
   re-juicio.
2. Este pre-registro se **commitea antes de medir**, como los cuatro anteriores de la serie.
3. La **métrica vieja se conserva** en el CSV, junto con `msf_k_sec`, para que cualquiera rehaga
   el juicio con la regla antigua.
4. El reporte publicará la **sensibilidad al umbral**, de modo que el veredicto no dependa de un
   número elegido a dedo.
5. **Si el resultado es negativo se reporta igual de fuerte que uno positivo.**
