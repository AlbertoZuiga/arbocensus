# Arbocensus — Frontend

Interfaz web del proyecto Arbocensus.

Stack: [Vite](https://vitejs.dev/) + [React 18](https://react.dev/) · [Tailwind CSS v3](https://tailwindcss.com/) · [axios](https://axios-http.com/) · [@tanstack/react-query](https://tanstack.com/query) · [react-router](https://reactrouter.com/) · [Leaflet](https://leafletjs.com/) (mapas, próximas PRs).

## Desarrollo con Docker (recomendado)

El servicio `frontend` está incluido en el `docker-compose.yml` de la raíz. Levanta toda la plataforma (backend, db, redis, osrm y frontend) con:

```bash
# desde la raíz del repo
make up          # asigna puertos libres en .env y levanta los servicios
```

| Servicio | URL                                            |
| -------- | ---------------------------------------------- |
| Frontend | [http://localhost:5173](http://localhost:5173) |
| API      | [http://localhost:8000](http://localhost:8000) |

El código se monta como volumen, por lo que el HMR de Vite recarga en caliente al editar archivos. `VITE_API_URL` se inyecta automáticamente apuntando al puerto del backend.

> Si cambias dependencias (`package.json`), reconstruye la imagen: `docker compose up -d --build frontend`.

## Desarrollo local (sin Docker)

```bash
cd frontend
cp .env.example .env       # ajusta VITE_API_URL si tu backend no está en :8000
npm install
npm run dev                # http://localhost:5173
```

El backend debe estar corriendo aparte (`docker compose up backend db`) para que las llamadas a la API funcionen.

## Scripts

```bash
npm run dev        # servidor de desarrollo (puerto fijo 5173)
npm run build      # build de producción a dist/
npm run preview    # sirve el build de producción localmente
npm run lint       # ESLint
```

## Variables de entorno

| Variable       | Default                     | Descripción                        |
| -------------- | --------------------------- | ---------------------------------- |
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL de la API DRF del backend |

## Estructura

```bash
frontend/
├── src/
│   ├── api/
│   │   ├── client.js       # única instancia axios (interceptores JWT + refresh)
│   │   └── tokenStore.js   # lectura/escritura de tokens en localStorage
│   ├── App.jsx             # shell de la app
│   ├── main.jsx            # QueryClientProvider + BrowserRouter + rutas
│   └── index.css           # directivas Tailwind
├── Dockerfile              # imagen de desarrollo (Vite + HMR)
├── eslint.config.js
├── tailwind.config.js
├── postcss.config.js
└── vite.config.js
```

## Convenciones

- Los datos del servidor viven en React Query, nunca en `useState`.
- Toda llamada HTTP usa la instancia de `api/client.js`; nunca `fetch` ni `axios` directo.
- GeoJSON usa `[lon, lat]`; Leaflet espera `[lat, lon]` — invertir al renderizar.
- Identificadores siempre en inglés; el texto de UI puede ir en español.
