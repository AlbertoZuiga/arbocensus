# Esquemas de Bases de Datos del Proyecto

Este directorio (`db_schemas`) contiene los esquemas de tres bases de datos utilizadas en distintas etapas y módulos del proyecto **Arbocensus**. Cada archivo proviene de consultas directas a las bases de datos en ejecución.

## 1. Arbocensus (Proyecto Original)

**URL de conexión:**  
`ARBOCENSUS_DB_URL=jdbc:postgresql://cdsk218k5hcni6.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d95dvg1udv7qqn`

**Archivo:**

- `arbocensus_schemas.csv`

Este esquema corresponde al proyecto original de Arbocensus, que continúa en funcionamiento y mantiene información activa en su base de datos.

---

## 2. Arbocensus API (Actualización del Proyecto)

**URL de conexión:**  
`ARBOCENSUS_API_DB_URL=jdbc:postgresql://arbocensus-dev.cwvglxcrsikm.us-east-2.rds.amazonaws.com:5432/arbocensus_api_dev`

**Archivo:**

- `arbocensus_api_schemas.csv`

Este esquema representa la versión actualizada del proyecto, también en ejecución y con datos activos.

---

## 3. Arbocensus Gamification (Integración Opcional)

**URL de conexión:**

`ARBOCENSUS_GAMIFICATION_DB_URL=jdbc:postgresql://arbocensus-dev.cwvglxcrsikm.us-east-2.rds.amazonaws.com:5432/arbocensus_gamification_dev`

**Archivo:**

- `arbocensus_gamification_schemas.csv`

Esta tercera integración permite asignar puntos a participantes dentro de una dinámica de gamificación basada en el escaneo de árboles.

---

## Cómo se obtuvieron los esquemas

Para extraer los esquemas de cada base de datos, se utilizó la siguiente consulta SQL, la cual lista esquemas, tablas y columnas de todas las tablas regulares:

```SQL
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
WHERE
    a.attnum > 0
    AND NOT a.attisdropped
    AND c.relkind = 'r' -- 'r' = tablas normales
ORDER BY
    n.nspname,
    c.relname,
    a.attnum;
```

---

Si se requiere actualizar los esquemas nuevamente, basta con ejecutar la consulta anterior en cada base de datos correspondiente.
