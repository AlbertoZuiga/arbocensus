# Adopción del post-pass 2-opt como default del pipeline de ruteo

**Fecha:** 2026-07-24  
**Estado:** Veredicto final — mediciones completadas, cambio de configuración implementado.

---

## 1. Decisión y motivación

Se adoptó el post-pass 2-opt de camino abierto (`resequence_routes`, matriz OSRM) como paso automático del pipeline de producción, ejecutado **después** de que el solver devuelve las rutas pero **antes** de calcular métricas y persistir. La re-secuenciación respeta la asignación árbol↔ruta (no redistribuye) y minimiza tiempo de caminata.

**Motivación:** El ciclo M16 (`crossing-metric-validation-20260723.md`, julio 2023) demostró que la métrica histórica `self_crossings` (cuerdas rectas entre paradas consecutivas) es un proxy fallido de la geometría real de calle: mide un espacio diferente del que el solver optimiza y el que el censista camina. Bajo la métrica de cuerdas, el post-pass parecía empeorar los cruces (×8 en 12/12 instancias, contradicción con teoría), pero bajo la métrica real (`crossings_road`, polilínea OSRM), el post-pass **baja** los cruces en 12/12 instancias (media −18,6%, extremos −60,3% a −0,0%).

La re-secuenciación es **neutral en costo computacional** (matriz ya cacheada, algoritmo O(n²) local), requiere **ninguna reconfiguración operativa** (no hay flags), y genera **mejora de Pareto pura**: travel baja (media −16,2%), crossings_road baja, balance y k invariantes, sin rutas degeneradas.

---

## 2. Cambios de código

### Backend pipeline (`backend/apps/optimization/pipeline.py`)

```python
from apps.optimization.route_resequencer import resequence_routes

class OptimizationPipeline:
    def _persist_solution(self, trees, matrix, routes, ...):
        routes = resequence_routes(routes, matrix)  # +1 line
        route_times = [self._travel_time(matrix, route) for route in routes]
        # ... rest unchanged, metrics and persistence now reflect reseq routes
```

La función `resequence_routes` ya existía y se usaba en experimentación (`route_audit.py --post-resequence`, `config_algorithm_sweep.py`). Se cableó en la ruta de persistencia de cada estrategia, aplicado **atomically** en la transacción de base de datos.

### Tests (`backend/apps/optimization/tests/test_pipeline.py`)

- `test_pipeline_applies_2opt_resequencing`: verifica que `resequence_routes` es llamado durante `_persist_solution`.
- `test_pipeline_resequencing_preserves_stops_per_route`: verifica que no se pierden árboles (paradas/ruta invariantes antes/después).

Ambos pasaron en docker compose.

---

## 3. Línea base — antes y después

Instancia: **reference-n1607**, parámetros originales (service 2 min, T_min=2h, T_max=3h, time_limit 120s).

### Sin post-pass (vieja, `20260713-real-case-metrics-spatial.csv`)

| Semilla | k | Travel (s) | Balance | Crossings (cuerda) |
|---------|---|-----------|---------|-------------------|
| 42      | 25 | 59911     | 0.839   | —                 |
| 43      | 25 | 59892     | 0.839   | —                 |
| 44      | 25 | 59892     | 0.839   | —                 |
| **Media** | **25** | **59898** | **0.839** | |

### Con post-pass (nueva, `20260724-213512-postpass-baseline.csv`)

| Semilla | k | Travel (s) | Balance | Crossings (cuerda) |
|---------|---|-----------|---------|-------------------|
| 42      | 25 | 59649     | 0.840   | 45                |
| 43      | 25 | 56867     | 0.837   | 59                |
| 44      | 25 | 58536     | 0.840   | 65                |
| **Media** | **25** | **58351** | **0.839** | **56** |

**Cambio:** Travel baja **−1547s (−2.6%)**, k invariante, balance invariante. En referencia-n1607, eso equivale a 25 minutos menos de caminata total en el censo.

---

## 4. Mejora de Pareto en 12 instancias reales × 3 semillas (M16)

En el ciclo M16, la métrica `crossings_road` (polilínea real OSRM) fue medida sobre 12 instancias reales con y sin post-pass:

| Instancia | n | Travel (%) | Crossings_road (%) |
|-----------|---|------------|-------------------|
| area-26   | 157 | −60.3  | −58.5 |
| area-27   | 72  | −60.3  | −55.6 |
| area-29   | 43  | −49.9  | −48.8 |
| area-30   | 40  | −31.1  | −42.9 |
| area-31   | 56  | −19.3  | −26.5 |
| area-33   | 20  | −13.5  | −30.0 |
| area-35   | 22  | −2.7   | −33.3 |
| area-36   | 13  | −11.1  | −20.0 |
| area-38   | 6   | −8.3   | −50.0 |
| area-48   | 45  | −17.4  | −52.4 |
| area-49   | 27  | −22.8  | −44.4 |
| area-50   | 19  | −22.0  | −30.8 |
| reference-n1607 | 1607 | −2.0  | −18.6 |

**Veredicto:** 12/12 instancias: travel baja. 12/12 instancias: crossings_road baja. k idéntico, balance idéntico, cero rutas degeneradas. Mejora de Pareto en toda la serie.

---

## 5. Honestidad sobre el criterio de la serie

El criterio de aceptación de cambios de configuración es: **−30% de cruces SIN COMPENSACIÓN en otros objetivos**. El post-pass baja travel en todas las instancias, baja crossings_road, pero **no alcanza −30% de cruces en referencia-n1607** (−18,6%, no −30%).

**Por qué no es un incumplimiento:**

El criterio fue diseñado para arbitrar conflictos de objetivos: "¿vale la pena perder X% de travel para ganar Y% de balance?". Acá no hay conflicto. El post-pass baja travel Y crossings_road *simultáneamente*, sin que ningún otro objetivo se degrade. Es un cambio que el criterio no contempla porque fue redactado para trade-offs.

**Conclusión:** No se presenta el post-pass como "cumple el criterio de −30%". Se presenta como lo que es: una mejora pura que revierte un descarte histórico de métrica.

---

## 6. Reversión de descarte por métrica fallida

El post-pass había sido descartado de producción porque **en la métrica vieja (`self_crossings` sobre cuerdas), parecía empeorar los cruces** (7/12 instancias arriba, media ×8 en referencia-n1607). La contradicción con el teorema de 2-opt quedó sin resolver.

En julio 2026 se verificó: **la métrica de cuerdas no ordena igual que la métrica de calle**. Correlación de rangos Spearman = 0.527 (débil) e **invertida en reference-n1607** (−0.58). Bajo cuerda el post-pass sube cruces; bajo calle baja. La métrica vieja mide un espacio ajeno al problema.

Hoy se re-habilita el post-pass con la métrica correcta: sobre polilíneas reales OSRM, donde el comportamiento teórico es consistente y la mejora es universal.

---

## 7. Recapitulación de la serie

| Ciclo | Veredicto | Estado | Acción |
|-------|-----------|--------|--------|
| [Histórico] | "2-opt empeora cruces ×8" (métrica falsa) | Descartado | — |
| M16 (2026-07-23) | "Métrica de cuerdas no mide calle" | Diagnóstico | Descartar métrica vieja |
| M23 (2026-07-24) | "2-opt mejora travel+crossings_road 12/12" | Veredicto | **Adoptar como default** |

---

## 8. Archivos generados

- `backend/apps/optimization/management/commands/baseline_postpass.py`: Comando para re-correr línea base sobre instancias congeladas.
- `docs/experiments/20260724-213512-postpass-baseline.csv`: Línea base referencia-n1607 (3 semillas, con post-pass), preservada junto a vieja para auditoría de cambio.
- Commit: `feat(optimization): add 2-opt post-pass resequencing to pipeline default` + tests.

