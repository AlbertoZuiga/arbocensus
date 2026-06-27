export default function RouteSelector({ routes, activeRouteId, onSelect }) {
  return (
    <div className="relative inline-block">
      <select
        value={activeRouteId}
        onChange={(event) => onSelect(event.target.value)}
        className="appearance-none bg-transparent pr-6 text-lg font-bold text-emerald-700 focus:outline-none"
      >
        {routes.map((route, index) => (
          <option key={route.id} value={route.id}>
            Ruta {index + 1} · {route.total_trees} árboles
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-emerald-700">
        ▾
      </span>
    </div>
  );
}
