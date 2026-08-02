# Arbocensus: Optimización de Rutas para Censo de Árboles Urbanos

Proyecto de Titulo - Ingeniería Civil en Ciencias de la Computación

- [Arbocensus: Optimización de Rutas para Censo de Árboles Urbanos](#arbocensus-optimización-de-rutas-para-censo-de-árboles-urbanos)
  - [Desarrollo Rápido](#desarrollo-rápido)
    - [Con Docker (recomendado)](#con-docker-recomendado)
      - [Datos de prueba (seed automático)](#datos-de-prueba-seed-automático)
    - [Desarrollo Local](#desarrollo-local)
    - [Comandos Comunes](#comandos-comunes)
    - [Estructura del Proyecto](#estructura-del-proyecto)
    - [Stack Técnico](#stack-técnico)
  - [Problema de Investigación](#problema-de-investigación)
  - [Contexto](#contexto)
  - [Enfoque de Solución](#enfoque-de-solución)

---

## Desarrollo Rápido

### Con Docker (recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/AlbertoZuiga/arbocensus-routing.git
cd arbocensus-routing

# 2. Configurar variables de entorno
cp .env.example .env

# 3. Descargar datos OSM para OSRM (primera vez, ~800 MB)
mkdir -p data/osm
curl -L https://download.geofabrik.de/south-america/chile-latest.osm.pbf \
     -o data/osm/chile-latest.osm.pbf

# 4. Levantar servicios (infra compartida + app de este worktree)
make up
```

OSRM procesa el PBF en el primer inicio (~10–15 min). Posterior a eso levanta en segundos.

Servicios disponibles:

| Servicio   | URL                                            |
| ---------- | ---------------------------------------------- |
| Frontend   | [http://localhost:5173](http://localhost:5173) |
| API Django | [http://localhost:8000](http://localhost:8000) |
| PostgreSQL | localhost:5432                                 |
| Redis      | localhost:6379                                 |
| OSRM       | [http://localhost:5000](http://localhost:5000) |

El frontend (Vite + React) corre con HMR dentro del contenedor `frontend`. Ver [`frontend/README.md`](frontend/README.md) para detalle y desarrollo local sin Docker.

#### Datos de prueba (seed automático)

Al levantar el backend, el `entrypoint` corre `seed_dev` de forma **idempotente**
(no recrea lo que ya existe): crea usuarios de prueba y un dataset *light* de
15 árboles **sin** ejecutar el solver. Desactívalo con `SEED_DEV=false` en `.env`.

| Usuario     | Rol      | Contraseña   |
| ----------- | -------- | ------------ |
| `admin1`    | admin    | `arbocensus` |
| `surveyor1` | surveyor | `arbocensus` |
| `surveyor2` | surveyor | `arbocensus` |

Cantidades y contraseña son configurables (`SEED_ADMIN_COUNT`,
`SEED_SURVEYOR_COUNT`, `SEED_USER_PASSWORD`, `SEED_DEV_TREES`). El superusuario
`admin` lo crea aparte el propio `entrypoint` (`DJANGO_SUPERUSER_*`).

### Desarrollo Local

```bash
# 1. Instalar dependencias (Python + Node + hooks de git)
./scripts/setup.sh
source .venv/bin/activate

# 2. Levantar la infra compartida (Postgres + OSRM) y el Redis de este worktree
make shared-up
docker compose up -d redis

# 3. Aplicar migraciones y levantar el servidor
cd backend
python manage.py migrate
python manage.py runserver
```

El script crea el `.venv`, instala `backend/dev-requirements.txt` (prod + dev) y ejecuta `npm install` (que configura Husky automáticamente).

Para agregar o actualizar dependencias Python, editar el `.in` correspondiente en `backend/` y recompilar:

```bash
cd backend
pip-compile requirements.in -o requirements.txt
pip-compile dev-requirements.in -o dev-requirements.txt
```

Las figuras de la tesis (`scripts/route_figures.py`) tienen su propio par `.in`/`.txt`, fuera del backend, y se recompilan desde la raíz:

```bash
pip-compile scripts/requirements-figures.in -o scripts/requirements-figures.txt
```

### Comandos Comunes

```bash
# Linting
npm run lint              # Ejecutar todos los linters
npm run lint:py           # Linting Python (ruff)
npm run lint:js           # Linting JavaScript/Markdown

# Formateo
npm run format            # Formatear código Python
npm run format:check      # Verificar formato sin cambiar

# Type checking
npm run type-check        # Verificar tipos con pyright

# Testing (dentro del contenedor backend — requiere GDAL + PostGIS)
make -C backend test                      # Todos los tests
make -C backend test ARGS="apps/optimization/tests"  # Subconjunto

# Django (desde backend/)
python manage.py migrate
python manage.py createsuperuser
celery -A config worker --loglevel=info

# Seed / datos (dentro del contenedor backend)
make seed                                         # seed_dev idempotente (usuarios + dataset light, sin solver)
python manage.py seed_demo --profile light        # 15 árboles, solo siembra (--no-optimize por defecto)
python manage.py seed_demo --profile medium       # 50 árboles + optimización (solver con tiempo automático)
python manage.py seed_demo --profile heavy        # 200 árboles + optimización
python manage.py seed_demo --distribution clustered --snap  # distribución realista + snap a calles (OSRM)
python manage.py baseline_sweep                   # barrido reproducible de calidad geográfica

# Análisis
python manage.py analyze_solution                 # métricas de la última solución
# Los informes de baseline_sweep / seed_demo se guardan en docs/experiments/.

# Tesis (LaTeX)
make -C docs/thesis pdf       # compila docs/thesis/main.pdf
make -C docs/thesis clean     # borra los artefactos (.aux, .log, ...)
```

> Los tests corren **dentro del contenedor backend**, no en el host. Los modelos
> geográficos (`PointField`) requieren GDAL y una base PostGIS, ambos provistos por
> la imagen `dev` y el servicio `db`. `make -C backend test` construye el target
> `dev` (con las dependencias de testing) y ejecuta pytest contra `db`.

La tesis compila con el `latexmk` local si existe (MacTeX) y, si no, cae a Docker
con una imagen TeX Live pineada por digest, sin necesidad de instalar TeX. En el
camino Docker la imagen se puede cambiar con `TEX_IMAGE`:
`make -C docs/thesis pdf TEX_IMAGE=texlive/texlive:latest` (con `latexmk` local la
variable no se usa).

### Estructura del Proyecto

```bash
.
├── backend/                  # Django + PostGIS API
│   ├── apps/
│   │   ├── accounts/         # Auth, CustomUser, roles
│   │   ├── datasets/         # Importación y gestión de árboles
│   │   ├── optimization/     # OR-Tools VRP solver, Celery jobs
│   │   └── routes/           # Soluciones y RouteStops
│   ├── config/               # Django settings, URLs, Celery
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # Vite + React + Tailwind (SPA)
│   ├── src/
│   │   ├── api/              # cliente axios (JWT) + token store
│   │   ├── App.jsx
│   │   └── main.jsx         # React Query + router
│   ├── Dockerfile
│   └── package.json
├── data/osm/                 # PBF para OSRM (ignorado en git)
├── docs/                     # Documentación y tesis
├── scripts/                  # Scripts de setup y utilidades
├── tools/
│   └── scripts/              # Scripts de lint, format, test
├── .github/                  # Workflows CI/CD
├── .husky/                   # Git hooks
├── docker-compose.yml        # App por worktree (backend/frontend/celery/redis)
├── docker-compose.shared.yml # Infra compartida (db + osrm)
├── pyproject.toml            # Ruff, pytest, pyright, coverage
└── package.json              # Commitlint, Husky, scripts npm
```

### Stack Técnico

**Backend (en desarrollo):**

- [Django 4.2](https://docs.djangoproject.com/) + [GeoDjango](https://docs.djangoproject.com/en/4.2/ref/contrib/gis/) — API REST con soporte geoespacial
- [PostGIS 3.3](https://postgis.net/) sobre PostgreSQL 15 — almacenamiento de geometrías
- [OR-Tools](https://developers.google.com/optimization) — solver VRP para optimización de rutas
- [Celery](https://docs.celeryq.dev/) + [Redis 7](https://redis.io/) — ejecución asíncrona de jobs de optimización
- [OSRM](http://project-osrm.org/) — matriz de costos de routing peatonal

**Frontend (en desarrollo):**

- [React 18](https://react.dev/) + [Vite](https://vitejs.dev/) — interfaz de usuario
- [Tailwind CSS](https://tailwindcss.com/) — estilos utility-first
- [@tanstack/react-query](https://tanstack.com/query) — estado de servidor
- [axios](https://axios-http.com/) — cliente HTTP con interceptores JWT
- [react-router](https://reactrouter.com/) — enrutamiento SPA
- [Leaflet](https://leafletjs.com/) — visualización de rutas y árboles en mapa

**Herramientas de desarrollo:**

- [Ruff](https://github.com/astral-sh/ruff) — linting y formateo Python
- [Pyright](https://github.com/microsoft/pyright) — type checking estático
- [Pytest](https://pytest.org/) + [Coverage.py](https://coverage.readthedocs.io/) — testing
- [Commitlint](https://commitlint.js.org/) + [Husky](https://typicode.github.io/husky/) — validación de commits

---

## Despliegue en Producción (DigitalOcean)

Stack: un droplet DigitalOcean (2 GB / 2 vCPU / 60 GB, ~$18/mes) con todo en `docker compose`. Caddy sirve el SPA y hace proxy al backend; TLS automático vía Let's Encrypt.

### Requisitos previos

**1. Llave SSH personal.** Es la que usarás tú para entrar al droplet por terminal. Si ya tienes una (`ls ~/.ssh/*.pub`), sáltate esto:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -C "tu-nombre"
```

La passphrase es opcional: protege la llave si te roban el equipo, pero te la pedirá en cada conexión.

**2. Llave SSH de deploy (opcional).** Es la que usa GitHub Actions para entrar al droplet. Por defecto la genera el propio `bootstrap-droplet.sh` y te imprime la privada al final, así que **no necesitas crearla acá**. Créala localmente solo si prefieres que la privada nunca pase por la consola web de DigitalOcean:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/arbocensus_deploy -N "" -C "github-actions"
```

Sin passphrase (`-N ""`) es obligatorio: Actions no puede escribir una passphrase interactiva.

**3. Al crear el droplet**, en la sección **Authentication → SSH Keys** agrega tu llave pública personal (`~/.ssh/id_ed25519.pub`). Si generaste la de deploy localmente, agrégala también: DO la copia a `/root/.ssh/authorized_keys` y el script te la ofrecerá en el menú, sin copiar y pegar nada. Sin ninguna llave, DO manda la contraseña de root por correo y solo queda la consola web.

> Un par **dedicado** para el deploy no es ceremonia: `DEPLOY_SSH_KEY` es una privada guardada en GitHub. Si ahí pones tu llave personal, cualquiera con acceso al repo —o un workflow comprometido— entra a todo lo que esa llave abre, no solo a este droplet. El script deja elegir tu llave personal, pero avisa.

**4. Dominio (opcional).** Apunta un registro A a la IP del droplet antes de correr el script. Sin dominio, el script usa `<IP>.sslip.io`, que resuelve solo y obtiene certificado de Let's Encrypt igual.

**5. Reserved IP (recomendado).** Gratis mientras esté asociada; permite rehacer el droplet sin cambiar el DNS ni el secreto `DEPLOY_HOST`.

### Provisionar el droplet (una vez)

Todo el aprovisionamiento vive en `scripts/bootstrap-droplet.sh`. En el panel de DigitalOcean: **Create → Droplet**, Ubuntu 24.04 LTS · Basic · 2 GB / 2 vCPU / 60 GB, región NYC3 o SFO3 (DO no tiene datacenter en Sudamérica).

Luego abre la consola web como `root` y corre estas tres líneas — no hay nada más manual:

```bash
apt-get update && apt-get install -y git
git clone https://github.com/AlbertoZuiga/arbocensus-routing.git /srv/arbocensus
bash /srv/arbocensus/scripts/bootstrap-droplet.sh
```

El script es idempotente (re-ejecutable tras un fallo) y hace, en orden:

1. Instala Docker, Compose, git, ufw, cron.
2. Crea 2 GB de swap — `osrm-extract` no cabe en 2 GB de RAM sin él.
3. Abre 22/80/443 en ufw.
4. Crea el usuario `deploy` y lo agrega al grupo `docker`. Para su llave SSH **pregunta** qué hacer, y entre las opciones lista las públicas que DigitalOcean ya instaló en `/root/.ssh/authorized_keys` al crear el droplet (con huella y comentario, para distinguirlas): elegir una de esas, generar un par nuevo en el droplet, pegar otra pública, o dejar la que ya esté autorizada.
5. Deja el checkout en `/srv/arbocensus` (el workflow hace `reset --hard` sobre él en cada deploy).
6. **Pregunta interactivamente** dominio, usuario/email/password de admin y las URLs de las bases legadas; genera `SECRET_KEY`, `DB_PASSWORD` y, si lo dejas vacío, el password de admin. Escribe `.env` con permisos `600`. Si `.env` ya existe, no lo toca.
7. Descarga el PBF de Chile y recorta el bbox del Gran Santiago (~326 MB de descarga, tarda).
8. Descarga las imágenes desde GHCR; si aún no están publicadas o son privadas, las construye en el droplet.
9. Levanta el stack.
10. Instala el cron de backup diario.

Al terminar imprime la IP, el usuario y —si generó el par— la clave privada de deploy: son exactamente los tres secretos de GitHub de la tabla de más abajo.

> El primer arranque de OSRM procesa el PBF y tarda 5-15 min en quedar `healthy`. El backend responde antes; la optimización de rutas no.

### Primer deploy

```bash
# Crear la rama production (la push dispara el workflow de deploy automáticamente)
git checkout -b production main
git push -u origin production
```

Después del primer push, proteger la rama en GitHub: PRs obligatorios, prohibir push directo, y los mismos checks requeridos que `main` — `lint`, `test`, `frontend`, `commitlint`. Un PR de release desde `main` los salta (los workflows se auto-excluyen), y un check saltado cuenta como aprobado para la protección de rama.

### Flujo de releases

```text
feat/x ──PR──> main ──PR "release: <resumen>"──> production ──push──> deploy.yml ──> droplet
```

```bash
# Abrir PR de release
gh pr create --base production --head main \
  --title "release: <resumen del cambio mayor>" \
  --body-file .github/PULL_REQUEST_TEMPLATE.md
```

Merge con **merge commit** (no squash). Hotfix: `fix/x` → PR a `main` → PR de release inmediato.

### Rollback

En GitHub → Actions → Deploy → `workflow_dispatch`, pasar el SHA de la imagen anterior como `image_tag`.

### Backups

El script deja el cron instalado (dump diario a las 03:00, retención 7 días). Para verificarlo o reinstalarlo a mano:

```bash
crontab -l   # debe listar la línea de pg-backup.sh
echo "0 3 * * * /srv/arbocensus/scripts/pg-backup.sh >> /var/log/arbocensus-backup.log 2>&1" | crontab -
```

Los dumps quedan en `/srv/arbocensus/backups/`, **en el mismo droplet**: no son un respaldo real hasta que salen de ahí. Copiarlos a otra máquina (`scp deploy@<host>:/srv/arbocensus/backups/ .`) o, mejor, configurar `rclone`/`s3cmd` contra DigitalOcean Spaces y encadenarlo al cron. Sin ese paso, un droplet destruido se lleva la base y los backups juntos. Los snapshots semanales de DO (~$3,6/mes) sí viven fuera del droplet y son el arreglo real.

### Secretos de GitHub requeridos

| Secreto          | Contenido                            |
| ---------------- | ------------------------------------ |
| `DEPLOY_HOST`    | IP del droplet                       |
| `DEPLOY_USER`    | Usuario SSH (ej. `deploy`)           |
| `DEPLOY_SSH_KEY` | Clave privada SSH del usuario deploy |

Los tres los imprime `bootstrap-droplet.sh` al terminar. La privada queda además en `/home/deploy/.ssh/arbocensus_deploy` del droplet.

El `GITHUB_TOKEN` automático de Actions publica y descarga las imágenes: no se necesita ningún PAT. El workflow hace `docker login ghcr.io` en el droplet con ese token efímero antes del `pull` y `docker logout` después, así que en el droplet no queda ninguna credencial de larga vida que expire sin aviso.

### Verificación post-deploy

```bash
# En el droplet
docker compose -f docker-compose.production.yml ps   # 6 servicios Up / healthy
curl https://<host>/api/                              # 200 o 401 (JWT requerido)
curl -k 'http://localhost:5000/nearest/v1/foot/-70.65,-33.45'  # OSRM Ok
```

### Reconfigurar variables

`.env` es la única fuente de configuración y `bootstrap-droplet.sh` no lo sobrescribe si existe. Para cambiar dominio, password o bases legadas: edítalo a mano (`.env.production.example` documenta cada variable) y `docker compose -f docker-compose.production.yml up -d`. Para regenerarlo desde cero, bórralo y re-ejecuta el script — genera secretos nuevos, incluida `SECRET_KEY`, lo que invalida todas las sesiones.

> **Importante**: el extracto OSM recortado invalida el caché SHA256 de la matriz respecto de los experimentos de la tesis. Los números de producción no son comparables con la suite congelada.

---

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
planificación eficiente de rutas para equipos de censistas.

Para esto, se cuenta con bases de datos previas que contienen:

- Fotografías de árboles urbanos
- Geolocalización de cada árbol
- Información técnica recopilada en censos anteriores

Sin embargo, estas fuentes de información se encuentran distribuidas en bases
separadas y heterogéneas. El proyecto busca utilizar dichos datos como entrada
para planificar recorridos eficientes de los censistas y facilitar futuras
integraciones con nuevas bases de datos.

La tarea de re-censo presenta desafíos importantes:

- **Ineficiencia en rutas**: Los censistas deben recorrer zonas extensas,
visitando árboles previamente registrados y nuevos puntos de interés
- **Balance de carga**: Es necesario distribuir equitativamente el trabajo
entre equipos de terreno considerando restricciones temporales por ruta
- **Actualización de información**: Se debe garantizar consistencia entre los
datos históricos y los nuevos registros
- **Complejidad combinatoria**: Encontrar rutas eficientes para múltiples
censistas corresponde a un problema NP-difícil
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

## Enfoque de Solución

El problema se modela como una variante del Multiple Traveling Salesman Problem
(mTSP) con restricciones temporales y balance de carga, resuelto mediante
programación con restricciones usando OR-Tools VRP.

El pipeline de optimización:

1. **Importación**: carga de árboles georreferenciados desde CSV o base de datos existente
2. **Matriz de costos**: consulta a OSRM para obtener tiempos de desplazamiento peatonal reales entre pares de árboles
3. **Solver VRP**: OR-Tools resuelve el ruteo multi-agente con restricciones de tiempo máximo por ruta y balance de carga
4. **Resultado**: conjunto de rutas asignadas a censistas, visualizadas en mapa con Leaflet
