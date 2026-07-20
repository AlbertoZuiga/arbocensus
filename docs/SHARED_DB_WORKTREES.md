# Worktrees compartiendo una sola base de datos

Varios worktrees corren en paralelo (dev local y experimentos:
`config_algorithm_sweep`, `objective_audit`) contra **una única** infra pesada
Postgres + OSRM. No hay stack "central" designado: **el primer worktree que hace
`make up` levanta la infra; los demás se enganchan**.

## Por qué

`docker-compose.shared.yml` declara el volumen `arbocensus_postgres_data` como
`external: true`: **todo** stack que declare `db` monta el *mismo* data dir. Dos
servicios `db` a la vez → dos procesos Postgres sobre el mismo WAL →
`PANIC: could not locate a valid checkpoint record`.

Solución: **solo la infra pesada** (`db + osrm`) se comparte, bajo un **nombre de
proyecto compose fijo** (`arbocensus`), así que existe **un** proceso Postgres y
**un** OSRM sin importar qué worktree los haya levantado. Compartir OSRM además
comparte la caché de matrices (tabla en Postgres) → aciertos en la suite
congelada de instancias. `db`/`osrm` se resuelven por nombre de servicio sobre la
red `arbocensus_default` (OSRM no publica puerto: la red interna es obligatoria).

### Redis y Celery NO se comparten

Cada worktree corre su **propio** `redis` + `celery` (y `backend`/`frontend`).
Un broker Redis compartido dejaría que el worker de un worktree **robe tasks**
encoladas por otro y ejecute el código equivocado sobre un `OptimizationJob` de
la db compartida. Redis es liviano y su volumen no es externo → sin conflicto.

Los servicios de app viven en una red **privada** por worktree
(`<proyecto>_default`, que lleva `redis` + `frontend`); `backend`/`celery` se unen
**además** a la red compartida `arbocensus_default` para alcanzar `db`/`osrm`.
Como la infra compartida no lleva redis, `redis` resuelve sin ambigüedad a la
instancia del worktree.

## Uso (Makefile)

Idéntico en cualquier worktree:

```bash
make up          # levanta infra compartida si falta, luego la app de este worktree
make up-build    # igual, forzando rebuild de la app
make down        # baja SOLO la app de este worktree; la infra sigue viva
make logs        # logs de la app de este worktree
make shared-down # DANGER: para la infra para TODOS los worktrees
```

- `make up` → target `shared-up`: si no hay `db` corriendo en el proyecto
  `arbocensus`, este worktree levanta `db+osrm` (con `--wait`, así el paso
  de migración no corre carrera con el initdb de Postgres) y luego migra + siembra
  la db compartida. Si ya está arriba, solo se engancha.
- El paso migrar+sembrar corre **cada vez que la infra estaba abajo** (no solo la
  primera): tras reiniciar el host se repite. `migrate` y `seed_dev` son
  idempotentes, así que es correcto — solo cuesta unos segundos.
- `shared-up` se serializa entre worktrees con un lock (`mkdir
  /tmp/arbocensus-shared-up.lock`). `docker compose up` **no** toma ningún lock
  propio: sin esto, dos `make up` simultáneos verían ambos la db abajo e
  intentarían crearla los dos. Si un `make up` muere de forma violenta y deja el
  lock colgado, borrarlo a mano: `rmdir /tmp/arbocensus-shared-up.lock`.
- `scripts/find-free-ports.sh` asigna `BACKEND_PORT`/`FRONTEND_PORT` libres por
  worktree en su `.env`, así múltiples backends coexisten sin chocar de puerto.
  **No** toca `DB_HOST_PORT`: la db es única y compartida, escanear la movería a
  5434 en el worktree que corra el script después de que la infra esté arriba.
  Para publicar el Postgres compartido en otro puerto, fijar `DB_HOST_PORT` a
  mano en el `.env` del worktree que levante la infra.
- Las imágenes se construyen por proyecto compose (sin tag fijo compartido): un
  `make up-build` en un worktree no puede pisar la imagen de otro y hacerle correr
  código ajeno contra la db compartida. La app monta el `./backend` del worktree
  encima de `/app`, así que el código vivo siempre es el de este worktree.

Verificar el nombre de la red si se cambia `SHARED_PROJECT`:

```bash
docker network ls | grep _default      # → arbocensus_default
```

### La red compartida debe existir primero

`docker-compose.yml` declara `arbocensus_default` como `external`, así que
**cualquier** `docker compose ...` en un worktree (incluidos `config`, `run` y las
recetas de experimentos de más abajo) falla si la infra nunca se levantó:

```
network arbocensus_default declared as external, but could not be found
```

Solución: `make shared-up` (o `make up`) primero.

## Experimentos (sin frontend/celery)

Para un barrido o auditoría puntual, contenedor efímero sin dependencias:

```bash
# Auditoría (read-only, no escribe en la db):
docker compose -p arbo-wt-<nombre> run --rm --no-deps backend \
  python manage.py objective_audit --dataset reference-n1607 \
    --output docs/experiments/audit_<nombre>.txt

# Barrido config × algoritmo × tamaño:
docker compose -p arbo-wt-<nombre> run --rm --no-deps backend \
  python manage.py config_algorithm_sweep --csv docs/experiments/sweep_<nombre>.csv
```

### Rutas de salida

Ambos comandos escriben bajo `settings.BASE_DIR.parent` (= raíz del contenedor).
El compose monta `./docs:/docs`, así que rutas como `docs/experiments/foo.csv` se
persisten en el `./docs` del worktree. **No** usar rutas fuera de `docs/` (p.ej.
`.local/…`): no están montadas y se pierden con el contenedor efímero.

## Seguridad en concurrencia

- **`config_algorithm_sweep`**: cada celda crea `RoutingConfig`/`OptimizationJob`/
  `RoutingSolution` con UUID nuevo dentro de un `transaction.atomic()` que termina
  en `raise _RollbackError` → **rollback total**, la db compartida no se ensucia
  con soluciones descartables. Cada corrida escribe a **su propio CSV** (`--csv`) y
  es reanudable (salta celdas ya presentes). Varios worktrees en paralelo con CSVs
  distintos no se pisan.
- **`objective_audit`**: read-only. Solo lee `Dataset`/`Tree`, arma la matriz OSRM
  y resuelve en memoria; no crea ni modifica ningún modelo.

## Reglas duras

- **NUNCA** `docker compose down -v` sobre la infra: destruye la db de todos los
  worktrees (por eso el Makefile no expone `down-v`).
- **NO** levantar dos servicios `db` a la vez. `docker-compose.yml` (la app de
  cada worktree) no define `db`; correr `docker compose up` a secas nunca arranca
  un segundo Postgres. `db` solo existe en `docker-compose.shared.yml`, que se usa
  únicamente con `-p arbocensus`.
- La infra compartida **no** debe incluir redis (por eso `shared-up` levanta solo
  `db osrm`): un redis en `arbocensus_default` colisionaría con el redis
  privado del worktree.
- Los servicios de app del worktree no migran ni siembran la db compartida
  (`RUN_MIGRATIONS=false`, `SEED_DEV=false`); eso ocurre solo en `shared-up`.
- `DB_PASSWORD` debe ser **idéntico** en el `.env` de todos los worktrees.
  Postgres solo usa `POSTGRES_PASSWORD` en el initdb, así que sobre un volumen ya
  poblado se ignora en silencio; pero cada worktree arma su `DATABASE_URL` con su
  propio `DB_PASSWORD`. Si uno derivó, ese worktree falla la autenticación sin
  ninguna pista de por qué.
- `make shared-down` usa `stop`, no `down`: `down` elimina la red
  `arbocensus_default`, que todos los demás worktrees declaran como `external`.

## Verificación real (ejecutada)

Ejecutado **antes** del renombre de archivos/proyecto (la infra se llamaba
`arbocensus` y la app del worktree vivía en `docker-compose.worktree.yml`); se
transcribe tal cual se corrió. Desde el worktree `shared-db-worktrees`,
contenedor efímero atado a la red compartida:

```
$ docker compose -f docker-compose.worktree.yml -p arbo-wt-shareddb \
    run --rm --no-deps backend python manage.py objective_audit \
    --dataset area-36-n13 --time-limit 5
[entrypoint] waiting for postgres at db:5432...
[entrypoint] postgres ready
# Auditoría de Objetivo — area-36-n13  (n=13)
...
**VEREDICTO: NO PAGAN — ... OR-Tools omite los costos de vehículos no usados.**
```

Conectó a `db/arbocensus` por nombre de servicio sobre la red compartida, sin
segundo proceso Postgres y sin WAL PANIC.
