import { PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";

export default function ProximityPanel({ stop, distance, inRange }) {
  if (!stop) return null;

  return (
    <div className="border-t border-slate-200 bg-white px-4 py-3">
      <p className="text-sm font-semibold text-slate-700">
        Próximo árbol {stop.sequence}
      </p>
      {distance == null ? (
        <p className="text-xs text-slate-500">Esperando ubicación GPS…</p>
      ) : (
        <p className={`text-xs font-medium ${inRange ? "text-emerald-600" : "text-amber-600"}`}>
          {inRange
            ? `A ${Math.round(distance)} m — en rango`
            : `A ${Math.round(distance)} m — fuera del rango de ${PROXIMITY_THRESHOLD_M} m`}
        </p>
      )}
    </div>
  );
}
