# Protocolo de ensayo y defensa — Demo end-to-end

Documento operativo para el ensayo previo y la presentación de defensa.
No reemplaza la documentación técnica; registra los pasos y precauciones
específicos para mostrar el sistema en vivo sin sorpresas.

---

## 1. Flujo demo end-to-end

El flujo completo cubre el ciclo de vida de una campaña de censo desde la
importación de datos hasta el seguimiento del avance.

### 1.1 Importar árboles desde la base legacy

1. En la barra superior, hacer clic en **Datasets**.
2. Hacer clic en **Importar desde Arbocensus** (botón superior derecho de
   la lista de datasets).
3. En la página de importación: seleccionar el área geográfica en el mapa
   o ajustar el bounding box para elegir el subconjunto de árboles a
   censar (≈ 12 946 registros QR disponibles en la base legacy).
4. Asignar un nombre al dataset y hacer clic en **Crear dataset**. El
   sistema aplica coincidencia espacial punto-en-polígono y redirige al
   detalle del nuevo dataset.

### 1.2 Explorar el dataset recién creado

El detalle del dataset muestra el mapa con los árboles importados. Desde
aquí se controla todo el ciclo de optimización, publicación y asignación.
No existe un paso separado de "crear dataset" — el dataset queda creado al
confirmar la importación en §1.1.

### 1.3 Optimizar rutas

1. En el detalle del dataset, hacer clic en **⚙ Optimización** (esquina
   superior derecha sobre el mapa).
2. Ajustar la config censal (ver §2) y hacer clic en **Optimizar**.
3. El solver OR-Tools corre en segundo plano vía Celery. El panel muestra
   el progreso y las pestañas de estrategia (Global / Término espacial /
   Cluster first) aparecen al completarse.
4. Esperar hasta que el estado cambie a **Completado**. No recargar la
   página; el panel se actualiza automáticamente.

### 1.4 Publicar la solución

1. Con el job completado, seleccionar la estrategia deseada en las
   pestañas sobre el mapa.
2. Hacer clic en **Publicar** (aparece junto a las pestañas de estrategia).
3. La solución queda publicada; a partir de aquí los censistas pueden ver
   sus rutas en la app móvil.

### 1.5 Asignar rutas a censistas

1. En el detalle del dataset, hacer clic en **👤 Asignación** (esquina
   superior derecha sobre el mapa).
2. En el panel de asignación, seleccionar cada ruta y elegir un censista
   del listado.
3. Confirmar. El censista recibe la ruta en su vista de mapa.

### 1.6 Censar con foto (flujo app / vista censista)

1. El censista inicia sesión en la app (misma URL, rol censista).
2. La página principal muestra su ruta asignada en el mapa.
3. El censista navega a cada árbol siguiendo el orden de la ruta, completa
   el formulario de observación y adjunta foto.
4. Al confirmar, el árbol queda marcado como **Visitado** y el registro
   queda en la base de datos.

### 1.7 Dashboard de avance

1. Desde el detalle del dataset, hacer clic en **📊 Avance** (esquina
   superior derecha).
2. El dashboard en `/admin/datasets/<id>/progress` muestra árboles
   visitados vs. pendientes por ruta y por censista, con mapa de puntos.
3. Activar **Mostrar rutas** en el mapa para superponer las líneas de ruta
   (esto dispara la llamada a OSRM — ver §3).

---

## 2. Config censal de referencia

Para la demo usar siempre:

| Parámetro | Valor de demo |
|-----------|--------------|
| Tiempo de servicio (`st`) | **2 minutos** por árbol |
| Tiempo máximo de ruta (`T_max`) | **3 horas** |

**Por qué estos valores y no los defaults de la UI**

Los defaults actuales de la interfaz son `st = 3 min` y `T_max = 2 h`,
elegidos como punto de partida conservador para árboles desconocidos.
Para la demo se usa una config más exigente porque:

- `st = 2 min` refleja el tiempo real medido en campo sobre el universo
  legacy (árboles ya conocidos, formulario corto).
- `T_max = 3 h` aprovecha la jornada completa y produce rutas con más
  nodos, lo que hace la optimización visualmente más interesante.
- Usar los defaults en vivo generaría rutas más cortas y menos
  representativas del caso de uso real.

Fijar estos valores por configuración explícita —en lugar de depender de
que el presentador los ingrese correctamente en el formulario— elimina el
riesgo de olvidar cambiarlos durante el nerviosismo de una presentación.
Si el stack tiene variables de entorno para estos parámetros, cargarlas
en el `.env` del perfil demo antes del ensayo.

---

## 3. Protocolo de warm-up de OSRM

### Por qué es necesario

El endpoint `/api/routes/geojson/?solution_id=<id>` llama a OSRM de forma
**síncrona** una vez por cada ruta en la solución (endpoint
`/route/v1/foot/`). No hay caché de geometrías entre llamadas — cada
request re-rutea desde OSRM. La latencia depende del estado del contenedor:

- **OSRM recién levantado (frío):** el primer request puede tardar varios
  segundos mientras carga el grafo de ruteo en memoria. Las llamadas
  sucesivas son rápidas una vez el grafo está en RAM.
- **OSRM con ≥ 1 h levantado (caliente):** el grafo ya está en memoria;
  todas las llamadas son sub-segundo.

### Tiempos medidos (ensayo 2026-07-18, OSRM ~20 h levantado)

| Dataset | Rutas | Llamada 1 | Llamada 2-3 |
|---------|-------|-----------|-------------|
| area-29-n43 (43 árboles) | 1 | ~120 ms | ~110 ms |
| reference-n1607 (1607 árboles) | 25 | ~410 ms | ~420 ms |

Con OSRM caliente el endpoint responde en menos de 500 ms incluso para
el dataset de referencia (1607 árboles, 25 rutas). El "warm-up" relevante
es el del **contenedor OSRM**, no de una caché de geometrías.

### Qué abrir y cuándo

**Al menos 5 minutos antes de comenzar la presentación:**

1. Abrir el navegador y navegar al detalle del dataset demo.
2. Hacer clic en **📊 Avance** para abrir el dashboard de progreso.
3. Activar **Mostrar rutas** en el mapa del dashboard.
4. Esperar a que las líneas de ruta aparezcan sobre el mapa.
5. Una vez visibles, **no cerrar esa pestaña**. Dejarla abierta en
   segundo plano.

Esa primera carga confirma que OSRM está healthy y el grafo en memoria.
Si la carga demora > 5 s, verificar el estado del contenedor (ver más abajo).

### Cómo forzar estado frío (para medir o reproducir)

Si se necesita verificar el comportamiento de arranque en frío **sin
afectar la base de datos**:

```bash
# Solo reinicia OSRM; no toca el volumen de Postgres
docker compose -p arbocensus restart osrm

# Esperar a que vuelva healthy (suele tardar 10-30 s según caché de SO)
docker compose -p arbocensus ps osrm

# Primera llamada frío — medir con curl:
curl -w "%{time_total}s\n" -o /dev/null -s \
  -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/routes/geojson/?solution_id=<id>"
```

### Señales de que el warm-up fue exitoso

- Las líneas de ruta aparecen sobre el mapa de Leaflet sin spinner
  prolongado (< 1 s con OSRM caliente).
- La consola del navegador no muestra errores 504 ni timeouts.

### Si el warm-up falla

Si el mapa no carga o muestra error en el paso de ensayo, **no continuar
con la demo en ese estado**. Verificar:

```bash
docker compose -p arbocensus ps        # todos deben estar healthy
docker compose -p arbocensus logs osrm --tail=20  # buscar errores de PBF
```

Nunca dejar el warm-up para el momento de la presentación.

---

## 4. Checklist pre-demo

Completar en orden; marcar cada ítem antes de comenzar.

### Infraestructura

- [ ] Un único stack Docker levantado (`docker compose -p arbocensus up -d`).
      No tener dos stacks activos simultáneamente — comparten el volumen
      de Postgres y pueden producir conflictos de WAL.
- [ ] Verificar que todos los servicios estén healthy:
      `docker compose -p arbocensus ps` → todos en estado `running` o `healthy`.
- [ ] Confirmar que OSRM respondió en la última prueba (ver §3).

### Datos

- [ ] Dataset demo creado desde la base legacy y visible en la lista de
      Datasets (`/admin/datasets`). Recomendado: seleccionar un área real
      de Santiago con 50–200 árboles para que la optimización tome < 2 min.
- [ ] Dataset optimizado con job en estado `completed`.
- [ ] Solución publicada. Verificar que el botón **Publicar** ya no
      aparece (indica que hay solución publicada).
- [ ] Rutas asignadas a al menos un censista de demo.
- [ ] Al menos una observación registrada (en la vista censista) para
      mostrar que el contador de visitados avanza en el dashboard de avance.
- [ ] Config censal (`st = 2 min`, `T_max = 3 h`) activa en el dataset
      que se va a mostrar (verificar en el historial de jobs del panel de
      Optimización).

> **Nota sobre `seed_demo`:** el comando
> `python manage.py seed_demo --profile medium` crea un dataset sintético
> de 70 árboles en Santiago y corre la optimización, pero **no** importa
> datos legacy, **no** publica la solución ni **no** crea asignaciones.
> Es útil para pruebas del solver, no para preparar el estado demo completo.

### Warm-up OSRM

- [ ] Dashboard de avance del dataset abierto en el navegador con rutas
      visibles en el mapa (ver §3).
- [ ] Líneas de ruta visibles en pantalla antes de comenzar.

### Presentación

- [ ] Pestaña del navegador con el dashboard de avance ya cargado.
- [ ] Otras pestañas o aplicaciones que puedan interrumpir (notificaciones,
      actualizaciones) silenciadas o cerradas.
- [ ] Resolución de pantalla verificada (el mapa de Leaflet debe verse
      completo sin scroll horizontal).
- [ ] Ensayo completo del flujo del punto 1 realizado al menos una vez
      antes de la defensa real.

---

## 5. Resultados del ensayo (2026-07-18)

Ensayo ejecutado contra el stack vivo en `localhost:8000` / `localhost:5173`
(~20 h de uptime, todos los servicios healthy).

### Flujo verificado

| Paso | Método de verificación | Resultado |
|------|----------------------|-----------|
| Importar legacy | API `GET /api/datasets/` — 23 datasets presentes, incluyendo `Arbocensus legacy test` (140 árboles) y `reference-n1607` (1607 árboles) | ✅ |
| Crear dataset | UI `/admin/datasets/legacy-import` carga áreas y árboles legacy desde `LEGACY_DB_URL` | ✅ |
| Optimizar | API `GET /api/optimization/jobs/` — múltiples jobs en estado `completed` | ✅ |
| Rutas y asignación | API `GET /api/routes/` — 432 rutas en DB | ✅ |
| Dashboard de avance | UI `/admin/datasets/<id>/progress` carga sin error; endpoint `GET /api/routes/progress/?dataset=<id>` responde | ✅ |
| GeoJSON de rutas | `GET /api/routes/geojson/?solution_id=<id>` responde (ver tiempos en §3) | ✅ |

### Divergencias corregidas en este documento

| Sección | Antes (incorrecto) | Después (corregido) |
|---------|-------------------|---------------------|
| §1.1 | "Importar datos" en menú lateral | Botón **Importar desde Arbocensus** en Datasets |
| §1.2 | "Datasets → Nuevo dataset" | Dataset se crea en el flujo LegacyImport (§1.1) |
| §1.3 | Botón "Optimizar" standalone | Panel **⚙ Optimización** en DatasetDetail |
| §1.5 | "Asignaciones" como sección | Panel **👤 Asignación** en DatasetDetail |
| §1.7 | Página "Historial" | Eliminado — no existe frontend de historial; usar dashboard de avance |
| §1.8 | URL `/routes/progress/` | URL `/admin/datasets/<id>/progress` |
| §4 checklist | `seed_demo` produce demo completa | `seed_demo` solo crea dataset sintético; no publica ni asigna |
