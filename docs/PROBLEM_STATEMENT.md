# Especificación del Problema

## Enunciado del Problema

Se dispone de un conjunto de puntos geográficos correspondientes a ubicaciones de árboles distribuidos en un área urbana. El objetivo es generar un conjunto de rutas óptimas que permitan a equipos de censadores visitar todos los puntos, minimizando el tiempo total de desplazamiento y manteniendo una distribución balanceada de la carga de trabajo.

Cada ruta representa el recorrido realizado por un equipo de censadores durante una jornada de trabajo. Las rutas no poseen un punto de inicio ni un punto de término predefinido; únicamente se requiere que los equipos recorran los árboles asignados.

## Definición Formal

### Entrada

- Conjunto de puntos:

$$
P = \{p_1, p_2, \ldots, p_n\}
$$

Donde cada punto $p_i$ corresponde a la ubicación geográfica de un árbol.

- Función de costo:

$$
c(p_i, p_j)
$$

Que representa el costo de desplazamiento entre los puntos $p_i$ y $p_j$.

La definición exacta del costo queda parametrizable y podrá depender de distintos criterios, tales como distancia geográfica, tiempo estimado de traslado, distancia sobre red vial u otras métricas relevantes para el problema (en principio se mediria usando el tiempo de distancia caminable de OSM).

- Tiempo de servicio:

$$
s
$$

Correspondiente al tiempo requerido para censar un árbol. Este valor se considera constante para todos los puntos.

- Restricciones temporales:

$$
T_{\min}, T_{\max}
$$

Donde:

$$
T_{\min} = 2h
$$

$$
T_{\max} = 3h
$$

Estos valores pueden parametrizarse según las necesidades operacionales.

## Restricciones

- Cada punto debe ser visitado exactamente una vez.
- Cada punto pertenece a una única ruta.
- Las rutas son abiertas: no existe un punto obligatorio de inicio ni de término.
- El tiempo total de cada ruta debe cumplir:

$$
T_{\min} \leq T_r \leq T_{\max}
$$

Donde:

$$
T_r =
\sum c(p_i, p_j) + m_r \cdot s
$$

Y $m_r$ corresponde a la cantidad de árboles asignados a la ruta $r$.

- La restricción temporal es dura: ninguna ruta puede exceder los límites establecidos.

## Objetivos

1. Minimizar el tiempo total de desplazamiento del conjunto de rutas.
2. Balancear la carga de trabajo entre rutas, minimizando diferencias significativas en tiempo total.

## Salida

- Conjunto de rutas:

$$
R = \{R_1, R_2, \ldots, R_k\}
$$

Donde cada ruta corresponde a una secuencia ordenada de puntos.

- El número de rutas $k$ no es conocido previamente y debe determinarse automáticamente de forma que todas las restricciones del problema sean satisfechas.

## Variantes del Problema Relacionadas

1. **Open mTSP (Multiple Traveling Salesman Problem abierto)**
   Múltiples rutas sin retorno obligatorio al origen.

2. **Time-Constrained Routing Problem**
   Rutas sujetas a límites temporales estrictos.

3. **Balanced Routing Problem**
   Optimización con balance de carga entre equipos.

4. **Capacitated Clustering + TSP**
   Estrategia heurística basada en agrupamiento previo y optimización local de rutas.
