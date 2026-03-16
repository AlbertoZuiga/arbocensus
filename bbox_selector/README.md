# Seleccionar caja delimitadora con Google Maps — `bbox_selector`

## Resumen

Aplicación pequeña en Flask para seleccionar visualmente una caja delimitadora (bounding box) sobre un mapa Google Maps (JavaScript) y mostrar los árboles dentro del área visible o del rectángulo dibujado. Las coordenadas del rectángulo se guardan en `saved_bbox.json`. El backend puede leer directamente de las bases `arbocensus` y `arbocensus-api` (JDBC o DSN) para devolver puntos de árboles vía el endpoint `/trees`.

Hechos relevantes:

- El cliente solicita `/trees` por la ventana de visualización (viewport) o por rectángulo dibujado y pinta marcadores SVG con ventanas de información (InfoWindow).
- Al guardar un bbox el cliente envía también la lista de árboles visibles y el servidor persiste ambos (si se envía) en `saved_bbox.json`.
- Orientado a Docker: `run.sh` ejecuta `docker compose` por defecto; usar `./run.sh --local` para ejecutar en `.venv`.

## Rápido: instalación y ejecución

1. Recomendado — Docker Compose (desarrollo):


```bash
cd bbox_selector
# opcional: cambiar puerto host (por defecto 5000)
HOST_PORT=5001 docker compose up --build
```

2. Local con `run.sh` (crea/usa `.venv` si pasas `--local`):

```bash
cd bbox_selector
./run.sh --local
```

3. Manual venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

4. Abrir en el navegador: `http://127.0.0.1:5000` (o `http://127.0.0.1:5001` si usaste `HOST_PORT=5001`).

## Endpoints principales

- `GET /` : Interfaz (mapa + herramientas de dibujo).
- `GET /trees?north=..&south=..&east=..&west=..&max=..` : devuelve `{ "ok": true, "trees": [...] }` con puntos `{lat,lng,meta}`.
- `POST /save` : recibe JSON con bbox `{north,south,east,west}` y opcional `trees: [...]` y persiste en `saved_bbox.json`.

Nota: el servidor intenta conectarse a las bases configuradas (si existen) y, si no puede, devuelve `trees: []`.

## Variables de entorno y `.env`

- `GOOGLE_API_KEY` (obligatorio para la UI).
- `ARBOCENSUS_API_DB_URL`, `ARBOCENSUS_DB_URL` (opcionales): DSN `postgres://...` o JDBC `jdbc:postgresql://...`.
- Si usas JDBC sin credenciales en la URL, utiliza `ARBOCENSUS_API_DB_URL_USER` / `ARBOCENSUS_API_DB_URL_PASSWORD` y equivalentes para la otra DB.
- `HOST_PORT` (opcional): puerto expuesto en el host para `docker compose` (mapeado a `5000` del contenedor).

Ejemplo mínimo `.env` (no commitear):

```.env
GOOGLE_API_KEY=YOUR_KEY_HERE
HOST_PORT=5001
ARBOCENSUS_API_DB_URL='postgres://user:pass@host:5432/db'
ARBOCENSUS_DB_URL='jdbc:postgresql://host:5432/db2'
ARBOCENSUS_DB_URL_USER='dbuser'
ARBOCENSUS_DB_URL_PASSWORD='dbpass'
```

El proyecto usa `python-dotenv` para cargar `.env` cuando ejecutas en modo local.

## Cómo funciona `/trees` (resumen técnico)

- `GET /trees?north=&south=&east=&west=&max=` filtra por la caja delimitadora usando `latitude BETWEEN south AND north` y `longitude BETWEEN west AND east`.
- El servidor prueba, en orden, `ARBOCENSUS_API_DB_URL` y luego `ARBOCENSUS_DB_URL` y consulta tablas conocidas (`arbocensus_api_app_sample` y `arbocensus_app_sample`).
- Los resultados se combinan y se deduplican por coordenadas (redondeo a 6 decimales).
- `max` limita el número de puntos retornados (por defecto 300) para evitar respuestas enormes.

Si tus tablas usan columnas distintas, indícalo y adapto las consultas.

## Guardado de bounding boxes y árboles

- Cuando el cliente guarda un rectángulo envía el bbox y (opcional) la lista de `trees` visibles; el servidor guarda el payload en `saved_bbox.json`.
- Ten en cuenta que si haces capturas con muchos puntos, `saved_bbox.json` puede crecer; si quieres puedo implementar truncado automático (por ejemplo N primeros puntos) o cambiar la estructura JSON.

Estructura actual guardada (ejemplo):

```json
{
  "north": -33.3,
  "south": -33.6,
  "east": -70.4,
  "west": -70.8,
  "trees": [ { "lat":..., "lng":..., "meta": {...} }, ... ]
}
```

## Docker y Docker Compose

- `Dockerfile` y `docker-compose.yml` incluidos. `docker compose` carga variables desde `.env` si lo especificas.
- Para evitar conflictos de puerto con servicios ya en el host, cambia `HOST_PORT` antes de levantar el stack:

```bash
HOST_PORT=5001 docker compose up --build
```

Comandos útiles:

```bash
# construir y levantar en primer plano
docker compose up --build

# en segundo plano
docker compose up --build -d

# ver logs
docker compose logs -f

# parar
docker compose down
```

## Pruebas

- Pruebas con `pytest` en `bbox_selector/tests`.
- Ejecutar en modo local (venv):

```bash
cd bbox_selector
./run.sh --local
.venv/bin/python -m pytest -q
```

Las pruebas actuales comprueban que la interfaz carga, que `/save` persiste correctamente y que `/trees` responde (sin requerir DB en el entorno de test).

## Recomendaciones y siguientes pasos

- Para muchas marcas en el mapa habilita clustering (MarkerClusterer) o implementa paginación en el servidor.
- Si prefieres que `saved_bbox.json` guarde solo `bbox` y mantenga `trees` en un archivo separado, o quieres truncado automático, lo implemento.
- Puedo añadir integración continua (CI, por ejemplo GitHub Actions) para ejecutar pruebas automáticamente.

## Seguridad

- No subir `.env` ni secretos al repositorio. Añade a `.gitignore`:

```.gitignore
.venv
.env
saved_bbox.json
secrets/
```

- Restringe la `GOOGLE_API_KEY` por referer en Google Cloud Console.

---
