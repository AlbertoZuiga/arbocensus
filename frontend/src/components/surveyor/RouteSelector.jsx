const MAX_CHIPS = 5;

export default function RouteSelector({ routes, activeRouteId, onSelect }) {
  if (routes.length <= 1) return null;

  if (routes.length > MAX_CHIPS) {
    return (
      <div className="border-b border-slate-200 bg-white px-4 py-2">
        <select
          value={activeRouteId}
          onChange={(event) => onSelect(event.target.value)}
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
        >
          {routes.map((route, index) => (
            <option key={route.id} value={route.id}>
              Ruta {index + 1} · {route.total_trees} árboles
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="flex gap-2 overflow-x-auto border-b border-slate-200 bg-white px-4 py-2">
      {routes.map((route, index) => {
        const active = route.id === activeRouteId;
        return (
          <button
            key={route.id}
            type="button"
            onClick={() => onSelect(route.id)}
            className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ${
              active ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-600"
            }`}
          >
            Ruta {index + 1} · {route.total_trees}
          </button>
        );
      })}
    </div>
  );
}
