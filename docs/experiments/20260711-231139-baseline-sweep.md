# Sweep estrategia × service_time × T_max

- Fecha (UTC): 2026-07-11T23:11:39+00:00
- Comando: `manage.py baseline_sweep`
- Parámetros:
- `dataset`: synthetic sizes=80
- `strategies`: global
- `service_time_min`: 5
- `t_max_h`: 3
- `seeds`: 5
- `base_seed`: 42
- `distribution`: uniform
- `time_limit_sec`: auto (cap 180)
- `csv`: /docs/experiments/20260711-231139-baseline-sweep.csv

## Métricas

| Métrica | Valor |
| --- | --- |
| corridas | 5 |
| csv | `/docs/experiments/20260711-231139-baseline-sweep.csv` |

## Qué ocurrió

Media por grupo:

| target | strategy | st [min] | T_max [h] | k | balance | T̄ [s] | σ [s] | >T_max | dropped | travel [s] | sum_rmax [m] | solap./ruta | IoU peor par | solve [s] | total [s] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n=80 | global | 5 | 3 | 8.0 | 0.884 | 7677 | 305 | 0.0 | 0.0 | 37423 | 11602 | 1.97 | 0.28 | 88.8 | 89.9 |

## Por qué ocurrió

_Pendiente de completar (rellenar tras analizar la corrida)._

## Posibles causas

_Pendiente de completar (rellenar tras analizar la corrida)._

## Hipótesis

_Pendiente de completar (rellenar tras analizar la corrida)._

## Cómo validar cada hipótesis

_Pendiente de completar (rellenar tras analizar la corrida)._

## Posibles soluciones o enfoques alternativos

_Pendiente de completar (rellenar tras analizar la corrida)._

## Métricas o experimentos recomendados para confirmar

_Pendiente de completar (rellenar tras analizar la corrida)._
