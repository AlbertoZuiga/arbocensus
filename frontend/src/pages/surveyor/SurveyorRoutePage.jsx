import { useMemo, useState } from "react";
import { useMyRoute, useRouteDetail } from "../../hooks/useMyRoute.js";
import { useWatchPosition } from "../../hooks/useWatchPosition.js";
import RouteMap from "../../components/surveyor/RouteMap.jsx";
import StopList from "../../components/surveyor/StopList.jsx";
import LogoutButton from "../../components/LogoutButton.jsx";

function CenteredMessage({ children }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-center">
      <p className="text-slate-500">{children}</p>
    </main>
  );
}

export default function SurveyorRoutePage() {
  const myRoute = useMyRoute();
  const routeId = myRoute.data?.[0]?.id;
  const routeDetail = useRouteDetail(routeId);
  const { position } = useWatchPosition();
  const [selectedStopId, setSelectedStopId] = useState(null);

  const stops = useMemo(() => routeDetail.data?.stops ?? [], [routeDetail.data]);

  const selectedStop = useMemo(() => {
    if (selectedStopId) {
      return stops.find((stop) => stop.id === selectedStopId) ?? null;
    }
    return stops.find((stop) => !stop.visited) ?? stops[0] ?? null;
  }, [stops, selectedStopId]);

  if (myRoute.isLoading || (routeId && routeDetail.isLoading)) {
    return <CenteredMessage>Cargando ruta…</CenteredMessage>;
  }
  if (myRoute.isError) {
    return <CenteredMessage>No se pudo cargar tu ruta.</CenteredMessage>;
  }
  if (!routeId) {
    return <CenteredMessage>No tienes ninguna ruta asignada.</CenteredMessage>;
  }

  const visitedCount = stops.filter((stop) => stop.visited).length;
  const progress = stops.length > 0 ? (visitedCount / stops.length) * 100 : 0;

  return (
    <main className="flex min-h-screen flex-col bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-emerald-700">
            Ruta {routeDetail.data?.route_number}
          </h1>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-500">
              {visitedCount}/{stops.length}
            </span>
            <LogoutButton />
          </div>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-emerald-600 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </header>

      <div className="h-[55vh] w-full">
        <RouteMap
          stops={stops}
          selectedStopId={selectedStop?.id ?? null}
          onSelectStop={setSelectedStopId}
          userPosition={position}
        />
      </div>

      <section className="flex-1 overflow-y-auto">
        <StopList
          stops={stops}
          selectedStopId={selectedStop?.id ?? null}
          onSelectStop={setSelectedStopId}
        />
      </section>
    </main>
  );
}
