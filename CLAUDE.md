# Arbocensus — Claude Code Instructions

Plataforma de optimización de rutas para censo de árboles urbanos.
Stack: Django 4.2 + PostGIS · OR-Tools · Celery + Redis · OSRM · React 18 + Vite · Leaflet.

---

## Identifiers and naming

- All identifiers in English: folders, modules, classes, variables, DB fields, API keys.
- Python: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- JavaScript/JSX: `camelCase` for functions/variables, `PascalCase` for components.
- Domain models: `Tree`, `Dataset`, `Route`, `RouteStop`, `RoutingConfig`, `OptimizationJob`, `RoutingSolution`.
- UI copy may be in Spanish; code identifiers never.

---

## Comments policy

Default: no comments.
Add a comment only when the WHY is non-obvious: a hidden constraint, a known bug workaround, a subtle invariant.
Never describe WHAT the code does — identifiers already do that.
Never add task references ("added for issue #X", "used by Y flow").

---

## No over-engineering

Do not add: error handling for impossible cases, fallbacks for internal code, feature flags, backwards-compatibility shims.
Do not design for hypothetical future requirements.
Three similar lines > premature abstraction.
No half-finished implementations with `...` or `pass` left in production code paths.

---

## Critical coordinate order — always verify

| System                 | Order                  | Example                        |
| ---------------------- | ---------------------- | ------------------------------ |
| OSRM URL               | `lon,lat`              | `/table/v1/foot/-70.65,-33.45` |
| GeoDjango `Point()`    | `Point(lon, lat)`      | `Point(-70.65, -33.45)`        |
| GeoDjango field access | `.x = lon`, `.y = lat` | `tree.location.y` → lat        |
| Leaflet                | `[lat, lon]`           | `[−33.45, −70.65]`             |
| GeoJSON geometry       | `[lon, lat]`           | `[-70.65, -33.45]`             |

Inverting these produces silently wrong results. Always check before submitting.

---

## OR-Tools VRP — mandatory patterns

- Dummy depot at index 0; real nodes at 1..N. Always subtract 1 when extracting: `manager.IndexToNode(index) - 1`.
- `AddDimension(callback, slack, capacity, fix_start_cumul_to_zero, name)` — parameter order is exact.
- `fix_start_cumul_to_zero=True` for open routes.
- `SetCumulVarSoftLowerBound` and `SetCumulVarSoftUpperBound` apply to `end_index`, not `start_index`.
- `SetFixedCostOfAllVehicles` value must exceed average arc cost × node count to have real effect.
- Filter empty routes from solution: only append if `route` list is non-empty after extraction.

---

## Celery tasks

- Import Django models INSIDE the task function body, never at module top-level (prevents circular imports on worker startup).
- Always call `job.set_status("running")` before any work, `job.set_error(str(exc))` before re-raising.

---

## Django conventions

- UUID primary keys on every model: `id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`.
- No `fields = "__all__"` in serializers — list fields explicitly.
- No business logic in views — views call models or pipeline; pipeline/models contain logic.
- `AUTH_USER_MODEL = "accounts.CustomUser"` — never use `django.contrib.auth.models.User` directly.
- GeoDjango: `PointField(srid=4326)` for all geographic coordinates.

---

## React conventions

- Server data lives in React Query, not `useState`. Never use `useState` for data fetched from API.
- Use the Axios instance from `api/client.js` (has JWT interceptors). Never use `fetch` or bare `axios`.
- Leaflet for all maps (MVP). No Google Maps in current scope.
- `refetchInterval` must return `false` (not just stop for `"completed"`): also stop for `"failed"` and `"error"`.
- GeoJSON coordinates are `[lon, lat]`; Leaflet expects `[lat, lon]` — invert when rendering.
