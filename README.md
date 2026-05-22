# Arbocensus: Optimización de Rutas para Censo de Árboles Urbanos

Proyecto de Titulo - Ingeniería Civil en Ciencias de la Computación

## Problema de Investigación

En trabajos previos de censo de árboles urbanos, equipos en terreno recorrieron
sectores de la ciudad para recopilar fotografías e información técnica de los
árboles. El objetivo principal de estos censos es contribuir a la seguridad
vial mediante el monitoreo y seguimiento del estado de árboles urbanos.

Los datos recopilados conforman una base inicial de información que podrá ser
utilizada en futuras etapas para apoyar el entrenamiento de modelos de
Inteligencia Artificial orientados a la clasificación y análisis de árboles
urbanos.

Actualmente, el proyecto se encuentra en una nueva etapa: realizar un
re-censo de las zonas previamente censadas. El objetivo es actualizar la
información existente, generar nuevos registros y mantener consistencia entre
los datos históricos y los nuevos datos recopilados en terreno mediante la
planificación eficiente de rutas para equipos de censadores.

Para esto, se cuenta con bases de datos previas que contienen:

- Fotografías de árboles urbanos
- Geolocalización de cada árbol
- Información técnica recopilada en censos anteriores

Sin embargo, estas fuentes de información se encuentran distribuidas en bases
separadas y heterogéneas. El proyecto busca utilizar dichos datos como entrada
para planificar recorridos eficientes de los censadores y facilitar futuras
integraciones con nuevas bases de datos.

La tarea de re-censo presenta desafíos importantes:

- **Ineficiencia en rutas**: Los censadores deben recorrer zonas extensas,
  visitando árboles previamente registrados y nuevos puntos de interés
- **Balance de carga**: Es necesario distribuir equitativamente el trabajo
  entre equipos de terreno considerando restricciones temporales por ruta
- **Actualización de información**: Se debe garantizar consistencia entre los
  datos históricos y los nuevos registros
- **Complejidad combinatoria**: Encontrar rutas eficientes para múltiples
  censadores corresponde a un problema NP-difícil
- **Costo operacional**: Reducir tiempos y costos de desplazamiento disminuye
  costos operacionales y fatiga del personal

## Contexto

El catastro y monitoreo de árboles urbanos es una tarea relevante principalmente
para la seguridad vial y la prevención de riesgos asociados a la caída de
árboles en zonas urbanas.

En etapas anteriores del proyecto, se realizaron censos en distintas zonas
urbanas para recopilar información visual y técnica de árboles. Estos datos
constituyen una base preliminar que permitirá, en etapas futuras, desarrollar
modelos de IA orientados a la clasificación y análisis de árboles urbanos.

En esta nueva etapa, se requiere volver a recorrer las zonas ya censadas para:

- Actualizar información existente
- Verificar el estado actual de los árboles
- Obtener nuevas fotografías y registros
- Generar información más completa y consistente para futuros procesos de clasificación mediante IA

El proyecto utilizará información proveniente de bases de datos existentes,
aunque también considera la posibilidad de integrar nuevas fuentes de datos en
el futuro.

La ausencia de rutas optimizadas para el re-censo puede generar jornadas de
trabajo extensas, desbalance entre equipos, aumento de costos operacionales y
menor eficiencia en la recolección de información en terreno.

## Enfoques de Solución Posibles

El problema puede modelarse como una variante de un problema de optimización
combinatoria sobre grafos, relacionado con el Multiple Traveling Salesman
Problem (mTSP) y problemas de routing con restricciones temporales y balance de
carga.

Dada la magnitud esperada del problema, una estrategia basada en optimización
exacta mediante solvers de programación matemática resulta especialmente
atractiva, permitiendo obtener soluciones óptimas o cercanas al óptimo sin
necesidad inmediata de heurísticas complejas.

### 1. Optimización Exacta mediante Solver

El problema puede formularse como un modelo de optimización combinatoria
entera-mixta (MILP), donde las variables representan asignaciones y recorridos
entre puntos.

Este enfoque permite incorporar restricciones temporales, balance de carga y
minimización de costos de desplazamiento utilizando solvers especializados como
OR-Tools, Gurobi, CBC o SCIP.

- **Ventajas**:
  - Soluciones óptimas o cercanas al óptimo
  - Modelamiento formal del problema
  - Fácil incorporación de restricciones

- **Desventajas**:
  - Escalabilidad limitada en instancias grandes
  - Mayor costo computacional en problemas de gran tamaño

### 2. Clustering Balanceado + Routing Local

- **Fase 1**: Particionar el área en clusters usando K-means o algoritmos
  geográficos
- **Fase 2**: Resolver rutas locales dentro de cada cluster
- **Ventajas**: Simple, escalable
- **Desventajas**: Soluciones locales, no optimiza globalmente

### 3. Meta-heurísticas

Búsqueda global con capacidad de escapar de óptimos locales (Genetic
Algorithm, Simulated Annealing, Ant Colony):

- **Ventajas**: Potencialmente mejores soluciones
- **Desventajas**: Mayor tiempo computacional, mayor complejidad

### 4. Algoritmos Exactos

Garantía de optimalidad en instancias pequeñas (Branch & Bound, Dynamic
Programming):

- **Ventajas**: Optimalidad garantizada
- **Desventajas**: Impracticable para grandes instancias

### 5. Enfoque Híbrido

Combinación de clustering, heurísticas y refinamiento local:

- **Ventajas**: Balance entre calidad y escalabilidad
- **Desventajas**: Mayor complejidad de implementación
