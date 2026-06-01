---
applyTo: "frontend/**"
---

# React Frontend Conventions

## Data fetching

Server state lives in React Query. Never use `useState` for data that comes from an API endpoint.

```jsx
// Correct
const { data, isLoading, error } = useQuery({
  queryKey: ["datasets"],
  queryFn: () => api.get("/datasets/").then(r => r.data),
});

// Wrong — do not do this
const [datasets, setDatasets] = useState([]);
useEffect(() => {
  fetch("/api/datasets/").then(...).then(setDatasets);
}, []);
```

Always use the Axios instance from `api/client.js`. It handles JWT injection and token refresh. Never use `fetch` or bare `axios.get`.

## Mutations

```jsx
const queryClient = useQueryClient();
const mutation = useMutation({
  mutationFn: (file) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/datasets/", form);
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["datasets"] });
    toast.success("Dataset imported");
  },
  onError: (err) => {
    toast.error(err.response?.data?.detail ?? "Import failed");
  },
});
```

## Polling for async jobs

Stop polling when status is terminal — both success AND failure:
```jsx
const { data: job } = useQuery({
  queryKey: ["job", jobId],
  queryFn: () => api.get(`/optimization/jobs/${jobId}/`).then(r => r.data),
  enabled: !!jobId,
  refetchInterval: (data) =>
    ["queued", "running"].includes(data?.status) ? 3000 : false,
  // stops on: "completed", "failed", "error", undefined
});
```

## Maps (Leaflet)

Leaflet uses `[lat, lon]`. GeoJSON uses `[lon, lat]`. Invert when rendering:
```jsx
// GeoJSON Point: coordinates = [lon, lat]
const leafletPos = [feature.geometry.coordinates[1], feature.geometry.coordinates[0]];

// Polyline from route GeoJSON
const positions = feature.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
```

Always set `height` on `MapContainer` — Leaflet renders nothing in a zero-height container:
```jsx
<MapContainer center={[-33.45, -70.65]} zoom={13} style={{ height: "500px" }}>
  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
</MapContainer>
```

Do not use Google Maps. Leaflet is the map library for this project.

## Component structure

Pages live in `src/pages/admin/` or `src/pages/surveyor/`.
Reusable components live in `src/components/`.
API functions live in `src/api/<resource>.js` (one file per Django app).

Page components own route-level state. Sub-components receive props; they do not call `useQuery` independently unless they are independently cacheable units.

## Loading and error states

Every data-fetching component must handle three states:
```jsx
if (isLoading) return <Skeleton />;
if (error) return <Alert variant="destructive">Failed to load: {error.message}</Alert>;
```

Use shadcn/ui components: `Button`, `Card`, `Badge`, `Table`, `Input`, `Alert`, `Skeleton`.
Tailwind for layout. No inline styles.

## Auth

JWT tokens are stored and refreshed by `api/client.js`. Components do not handle tokens.
`ProtectedRoute` redirects to `/login` if no valid token. Role check (`admin` vs `surveyor`) also in `ProtectedRoute`.

```jsx
<Route element={<ProtectedRoute requiredRole="admin" />}>
  <Route path="/admin/*" element={<AdminLayout />} />
</Route>
```
