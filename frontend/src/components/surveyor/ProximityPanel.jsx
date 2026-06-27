import { PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";

export default function ProximityPanel({ stop, distance, inRange, onVisit, isVisiting }) {
  if (!stop) return null;

  return (
    <div className="flex shrink-0 items-center gap-3 border-t border-slate-200 bg-white px-4 py-3">
      <div className="flex-1">
        <p className="text-sm font-semibold text-slate-700">
          Próximo árbol {stop.sequence}
        </p>
        {distance == null ? (
          <p className="text-xs text-slate-500">Esperando ubicación GPS…</p>
        ) : (
          <p
            className={`text-xs font-medium ${inRange ? "text-emerald-600" : "text-amber-600"}`}
          >
            {inRange
              ? `A ${Math.round(distance)} m — en rango`
              : `A ${Math.round(distance)} m — fuera del rango de ${PROXIMITY_THRESHOLD_M} m`}
          </p>
        )}
      </div>
      <a
        href={`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lon}&travelmode=walking`}
        target="_blank"
        rel="noreferrer"
        className="rounded border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-600"
      >
        Navegar
      </a>
      {stop.visited ? (
        <span className="rounded bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-700">
          Visitado
        </span>
      ) : (
        <button
          type="button"
          onClick={() => onVisit(stop.id)}
          disabled={isVisiting}
          className={`rounded px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
            inRange ? "bg-emerald-700" : "bg-amber-600"
          }`}
        >
          {inRange ? "Marcar visitado" : "Marcar de todos modos"}
        </button>
      )}
    </div>
  );
}
