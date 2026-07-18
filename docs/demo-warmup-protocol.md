# Protocolo de ensayo y defensa — Demo end-to-end

Documento operativo para el ensayo previo y la presentación de defensa.
No reemplaza la documentación técnica; registra los pasos y precauciones
específicos para mostrar el sistema en vivo sin sorpresas.

---

## 1. Flujo demo end-to-end

El flujo completo cubre el ciclo de vida de una campaña de censo desde la
importación de datos hasta el seguimiento del avance.

### 1.1 Importar árboles desde la base legacy

1. Abrir **Importar datos** en el menú lateral.
2. Seleccionar fuente **Legacy** y elegir el universo de árboles ya
   geocodificados (≈ 12 946 registros QR disponibles).
3. Confirmar importación. El sistema aplica coincidencia espacial
   punto-en-polígono para asignar cada árbol a su área.

### 1.2 Crear dataset de trabajo

1. Ir a **Datasets → Nuevo dataset**.
2. Nombrar el dataset y seleccionar el subconjunto de árboles a censar
   (e.g., un área o grupo de IDs).
3. Guardar. El dataset queda en estado *borrador* hasta que se optimiza.

### 1.3 Optimizar rutas

1. Abrir el dataset creado y hacer clic en **Optimizar**.
2. El solver OR-Tools genera las rutas y las asocia al dataset.
3. Esperar hasta que el estado cambie a **Completado** (el panel se
   actualiza automáticamente; no recargar manualmente).

### 1.4 Publicar el dataset

1. Con el dataset optimizado, hacer clic en **Publicar**.
2. El estado pasa a *publicado*; a partir de aquí los censistas pueden
   ver sus rutas asignadas en la app móvil.

### 1.5 Asignar rutas a censistas

1. Ir a **Asignaciones** dentro del dataset.
2. Seleccionar cada ruta y asignar un censista del listado.
3. Confirmar. El censista recibe la ruta en su vista de mapa.

### 1.6 Censar con foto (flujo app / vista censista)

1. El censista abre su ruta asignada en el mapa.
2. Navega al próximo árbol siguiendo el orden de la ruta.
3. Al llegar al árbol, completa el formulario de observación y adjunta foto.
4. Marcar árbol como **Censado**. El registro queda en historial.

### 1.7 Historial de observaciones

- Abrir **Historial** para ver todas las observaciones registradas con
  foto, fecha, censista y árbol asociado.
- Filtrar por dataset o por censista para verificar cobertura.

### 1.8 Dashboard de avance

- Ir a **Avance** (o abrir `/routes/progress/` directamente).
- El dashboard muestra árboles completados vs. pendientes por ruta y por
  censista, actualizado en tiempo real.

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

El endpoint `/api/routes/geojson/` llama a OSRM de forma **síncrona** en
la primera solicitud. OSRM no mantiene un caché precalentado entre
reinicios del contenedor, así que la primera llamada puede tardar varios
segundos o decenas de segundos dependiendo del tamaño del dataset. En
vivo, ese silencio mientras el mapa carga resulta incómodo.

### Qué abrir y cuándo

**Al menos 5 minutos antes de comenzar la presentación:**

1. Abrir el navegador y navegar a la **vista de mapa del dataset demo**
   (la misma vista que se mostrará en vivo).
2. Esperar a que el mapa cargue completamente con las rutas trazadas
   (las líneas de ruta deben verse en pantalla).
3. Una vez cargado, **no cerrar esa pestaña**. Dejarla abierta en
   segundo plano.

Esa primera carga dispara la llamada a OSRM y llena el caché interno.
Las llamadas posteriores durante la presentación responden en milisegundos.

### Señales de que el warm-up fue exitoso

- Las líneas de ruta aparecen sobre el mapa de Leaflet sin spinner
  prolongado.
- La consola del navegador no muestra errores 504 ni timeouts.

### Si el warm-up falla

Si el mapa no carga o muestra error en el paso de ensayo, **no continuar
con la demo en ese estado**. Verificar que el contenedor OSRM esté
corriendo (`docker ps`) y reintentar. Nunca dejar el warm-up para
el momento de la presentación.

---

## 4. Checklist pre-demo

Completar en orden; marcar cada ítem antes de comenzar.

### Infraestructura

- [ ] Un único stack Docker levantado (`docker compose up -d`). No tener
      dos instancias del stack activas simultáneamente — comparten el
      volumen de Postgres y pueden producir conflictos de WAL.
- [ ] Verificar que todos los servicios estén healthy:
      `docker compose ps` → todos en estado `running` o `healthy`.
- [ ] Confirmar que OSRM respondió en la última prueba (ver sección 3).

### Datos

- [ ] Perfil demo ya sembrado en la base de datos:
      usuario censista de demo, dataset optimizado y publicado con
      asignaciones listas.
- [ ] Al menos una observación con foto pre-cargada para mostrar
      historial sin tener que crear una en vivo.
- [ ] Config censal (`st = 2 min`, `T_max = 3 h`) activa en el dataset
      que se va a mostrar.

### Warm-up OSRM

- [ ] Vista de mapa del dataset abierta en el navegador (ver sección 3).
- [ ] Rutas visibles en pantalla antes de comenzar.

### Presentación

- [ ] Pestaña del navegador con el mapa ya cargado en primer plano.
- [ ] Otras pestañas o aplicaciones que puedan interrumpir (notificaciones,
      actualizaciones) silenciadas o cerradas.
- [ ] Resolución de pantalla verificada (el mapa de Leaflet debe verse
      completo sin scroll horizontal).
- [ ] Ensayo completo del flujo del punto 1 realizado al menos una vez
      antes de la defensa real.
