export default function StopList({
  stops,
  selectedStopId,
  nextPendingStopId,
  onSelectStop,
}) {
  return (
    <ul className="divide-y divide-slate-100">
      {stops.map((stop) => {
        const selected = stop.id === selectedStopId;
        const locked =
          !stop.visited && nextPendingStopId != null && stop.id !== nextPendingStopId;
        return (
          <li key={stop.id}>
            <button
              type="button"
              onClick={() => onSelectStop(stop.id)}
              className={`flex w-full items-center gap-3 px-4 py-3 text-left ${
                selected ? "bg-blue-50" : "bg-white"
              } ${locked ? "opacity-60" : ""}`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${
                  stop.visited ? "bg-emerald-600" : selected ? "bg-blue-600" : "bg-slate-500"
                }`}
              >
                {stop.sequence}
              </span>
              <span className="flex-1 text-sm text-slate-700">Árbol {stop.sequence}</span>
              {stop.visited ? (
                <span className="text-xs font-semibold text-emerald-600">Visitado</span>
              ) : (
                stop.id === nextPendingStopId && (
                  <span className="text-xs font-semibold text-amber-600">Siguiente</span>
                )
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
