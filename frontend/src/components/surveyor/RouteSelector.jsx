export default function RouteSelector({ routes, activeRouteId, onSelect }) {
  if (routes.length <= 1) return null;

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
