# Instancias congeladas

CSV versionados con las instancias reales usadas en los experimentos. Reemplazan a
la base de datos legacy como fuente de verdad: los experimentos se reproducen desde
este directorio, sin conexión externa.

## Cómo cargarlas

```bash
docker compose up -d
docker compose exec backend python manage.py load_instances
```

Carga todos los CSV como datasets (el nombre del dataset es el nombre del archivo sin
extensión). Para cargar solo algunos:

```bash
docker compose exec backend python manage.py load_instances /docs/experiments/instances/reference-n1607.csv
```

El comando es idempotente: volver a cargar la misma instancia no duplica árboles ni
cambia sus identificadores.

## Formato

Una fila por árbol, columnas `source,external_id,lat,lon,species`. Solo geometría,
especie e identificador de origen; sin fotos, usuarios ni observaciones.

`species` viene vacía en las 429 filas `legacy_api`: la columna `tree_species` de la
base legacy es `NULL` en todas ellas. La columna se mantiene porque es parte del
esquema, no porque el snapshot tenga datos.

## Identificadores deterministas

El UUID de cada dataset es `uuid5(INSTANCE_NAMESPACE, "instance:<slug>")` y el de
cada árbol es `uuid5(<uuid del dataset>, "<source>:<external_id>")`. Son función pura
del CSV, así que la misma instancia produce los mismos UUID en cualquier worktree o
máquina. Eso estabiliza el `source_hash` de `DistanceMatrix` (SHA-256 sobre los UUID
ordenados), y la matriz de costos OSRM se reutiliza entre corridas en vez de
recalcularse en frío.

El UUID del árbol se ancla al dataset, no solo a `(source, external_id)`, porque las
áreas legacy se solapan: las 12 áreas suman 520 filas sobre 429 árboles distintos, y
la referencia repite esos mismos árboles. Un UUID global colisionaría al cargar dos
instancias que comparten un árbol en la misma base.

## Procedencia

Volcado desde la base legacy (Heroku, solo lectura) con:

```bash
docker compose exec backend python manage.py freeze_legacy
```

Requiere `ARBOCENSUS_API_DB_URL` y `ARBOCENSUS_DB_URL` en `.env`. Es el único paso que
toca la base legacy, y solo hace falta si hay que regenerar los CSV.

Dos fuentes:

- `legacy_api` — 429 árboles con área asignada por punto en polígono.
- `legacy_app` — 1178 árboles reconstruidos desde `mltree`/`qr`, con la mediana de
  las coordenadas de sus muestras. No tienen área.

`reference-n1607.csv` es la unión de ambas fuentes.

Las áreas legacy se recrean en cada campaña que las usa (48 registros, 27 sin
árboles, 21 no vacíos repartidos en 10 campañas), y los nombres se reciclan entre
geometrías distintas: hay tres áreas llamadas "Area 1" con polígonos diferentes. La
unidad útil es el área deduplicada por geometría; el volcado se queda con el registro
de menor `id` de cada polígono, que es el que da nombre al archivo.

| Archivo             |    n | Área legacy | Campaña de origen     |
| ------------------- | ---: | ----------- | --------------------- |
| `area-26-n157.csv`  |  157 | Area 1      | Campaña Semiponti     |
| `area-27-n72.csv`   |   72 | Area 2      | Campaña Semiponti     |
| `area-31-n56.csv`   |   56 | Area 5      | Campaña Semiponti     |
| `area-48-n45.csv`   |   45 | Area 1      | Campaña Defensa 2024  |
| `area-29-n43.csv`   |   43 | Area 3      | Campaña Semiponti     |
| `area-30-n40.csv`   |   40 | Area 4      | Campaña Semiponti     |
| `area-49-n27.csv`   |   27 | Area 2      | Campaña Defensa 2024  |
| `area-35-n22.csv`   |   22 | Area 8      | Campaña Semiponti     |
| `area-33-n20.csv`   |   20 | Area 7      | Campaña Semiponti     |
| `area-50-n19.csv`   |   19 | Area 3      | Campaña Defensa 2024  |
| `area-36-n13.csv`   |   13 | Area 9      | Campaña Semiponti     |
| `area-38-n6.csv`    |    6 | Area 11     | Campaña Semiponti     |
| `reference-n1607.csv` | 1607 | —         | `legacy_api` + `legacy_app` |

## Batería de crecimiento

Serie de instancias reales de tamaño creciente para medir cómo escalan los
algoritmos. Reemplaza al disperso sintético por densidad real.

El universo son los 12.946 árboles georreferenciados de la app (fuente `legacy_app`):
un árbol por QR, ubicado en la mediana de `latitude`/`longitude` de sus muestras. Se
filtra `qr` no vacío y coordenadas dentro del recuadro de Chile continental
(`latitude BETWEEN -56 AND -17`, `longitude BETWEEN -76 AND -66`).

Construcción:

- **Semilla**: centroide (media de lat/lon) de esos 12.946 puntos,
  `(-33.41947947204772, -70.56545962517218)`. Se guarda como constante en el código
  (`instances.BATTERY_SEED`), no se recalcula, para que el orden no se mueva si la
  base legacy cambia.
- **Orden**: todos los árboles ordenados por distancia haversine a la semilla, con
  desempate por `external_id`. Determinista y total.
- **Anidamiento**: `battery-n{n}` es el prefijo de los primeros `n` de esa lista, para
  `n ∈ {50, 100, 200, 400, 800, 1000}`. Cada instancia es prefijo exacto (byte a byte)
  de la siguiente: `n50 ⊂ n100 ⊂ … ⊂ n1000`. Así el crecimiento es puramente espacial
  —añadir árboles más lejanos— y no una muestra distinta.
- **Variantes dispersas**: sobre los primeros 1000, se toma 1 de cada 2
  (`battery-sparse-n500`) y 1 de cada 4 (`battery-sparse-n250`). Misma extensión
  espacial que `n=1000`, densidad a la mitad y a un cuarto: aíslan el efecto de la
  densidad del efecto del tamaño.

Los tamaños son geométricos (≈×2), no aritméticos, a propósito: los cambios de régimen
y el número de vehículos/clusters `k` escalan multiplicativamente con `n`, no en pasos
fijos. Una grilla aritmética (50, 100, 150, …) gastaría corridas amontonando puntos en
un mismo régimen y sin llegar a los tamaños grandes; la geométrica cubre dos órdenes de
magnitud con seis corridas.

Formato idéntico al resto: `source=legacy_app`, `external_id=qr`, `species` vacía. Las
filas van en orden de distancia a la semilla (no re-ordenadas por `external_id`), que
es lo que hace que los archivos sean prefijos literales entre sí.

| Archivo                  |    n | Densidad | Contenido                       |
| ------------------------ | ---: | -------- | ------------------------------- |
| `battery-n50.csv`        |   50 | plena    | 50 más cercanos a la semilla    |
| `battery-n100.csv`       |  100 | plena    | prefijo, primeros 100           |
| `battery-n200.csv`       |  200 | plena    | prefijo, primeros 200           |
| `battery-n400.csv`       |  400 | plena    | prefijo, primeros 400           |
| `battery-n800.csv`       |  800 | plena    | prefijo, primeros 800           |
| `battery-n1000.csv`      | 1000 | plena    | prefijo, primeros 1000          |
| `battery-sparse-n500.csv`|  500 | 1/2      | 1 de cada 2 sobre los 1000      |
| `battery-sparse-n250.csv`|  250 | 1/4      | 1 de cada 4 sobre los 1000      |

Regeneración (único paso que toca la base legacy, requiere `ARBOCENSUS_DB_URL`):

```bash
docker compose exec backend python manage.py freeze_legacy --battery
```
