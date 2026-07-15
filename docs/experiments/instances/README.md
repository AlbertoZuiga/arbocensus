# Instancias congeladas

CSV versionados con las instancias reales usadas en los experimentos. Reemplazan a
la base de datos legacy como fuente de verdad: los experimentos se reproducen desde
este directorio, sin conexión externa.

## Cómo cargarlas

```bash
docker compose up -d
docker compose exec backend python manage.py load_instances
```

Carga los 13 CSV como datasets (el nombre del dataset es el nombre del archivo sin
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
