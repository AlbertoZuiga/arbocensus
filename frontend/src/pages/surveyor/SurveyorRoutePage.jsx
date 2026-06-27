import { useMemo, useState } from "react";
import { useMyRoute, useRouteDetail } from "../../hooks/useMyRoute.js";
import { useWatchPosition } from "../../hooks/useWatchPosition.js";
import { useVisitStop } from "../../hooks/useVisitStop.js";
import { useWakeLock } from "../../hooks/useWakeLock.js";
import RouteMap from "../../components/surveyor/RouteMap.jsx";
import RouteSelector from "../../components/surveyor/RouteSelector.jsx";
import StopList from "../../components/surveyor/StopList.jsx";
import ProximityPanel from "../../components/surveyor/ProximityPanel.jsx";
import LogoutButton from "../../components/LogoutButton.jsx";
import { haversineMeters, PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";

function CenteredMessage({ children }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-center">
      <p className="text-slate-500">{children}</p>
    </main>
  );
}

export default function SurveyorRoutePage() {
  const myRoute = useMyRoute();
  const routes = useMemo(
    () => [...(myRoute.data ?? [])].sort((a, b) => a.route_number - b.route_number),
    [myRoute.data]
  );

  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const activeRouteId =
    routes.find((route) => route.id === selectedRouteId)?.id ?? routes[0]?.id;
  const activeIndex = routes.findIndex((route) => route.id === activeRouteId);

  const routeDetail = useRouteDetail(activeRouteId);
  const { position } = useWatchPosition();
  const visitMutation = useVisitStop(activeRouteId);
  useWakeLock();
  const [selectedStopId, setSelectedStopId] = useState(null);

  const stops = useMemo(() => routeDetail.data?.stops ?? [], [routeDetail.data]);

  const selectedStop = useMemo(() => {
    if (selectedStopId) {
      return stops.find((stop) => stop.id === selectedStopId) ?? null;
    }
    return stops.find((stop) => !stop.visited) ?? stops[0] ?? null;
  }, [stops, selectedStopId]);

  const distance = useMemo(() => {
    if (!position || !selectedStop) return null;
    return haversineMeters(
      position.lat,
      position.lon,
      selectedStop.lat,
      selectedStop.lon
    );
  }, [position, selectedStop]);

  const inRange = distance != null && distance <= PROXIMITY_THRESHOLD_M;

  if (myRoute.isLoading || (activeRouteId && routeDetail.isLoading)) {
    return <CenteredMessage>Cargando ruta…</CenteredMessage>;
  }
  if (myRoute.isError) {
    return <CenteredMessage>No se pudo cargar tu ruta.</CenteredMessage>;
  }
  if (!activeRouteId) {
    return <CenteredMessage>No tienes ninguna ruta asignada.</CenteredMessage>;
  }

  const visitedCount = stops.filter((stop) => stop.visited).length;
  const progress = stops.length > 0 ? (visitedCount / stops.length) * 100 : 0;

  const handleSelectRoute = (routeId) => {
    setSelectedRouteId(routeId);
    setSelectedStopId(null);
  };

  return (
    <main className="flex min-h-screen flex-col bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-emerald-700">
              Ruta {activeIndex + 1}
            </h1>
            <p className="text-xs text-slate-500">{stops.length} árboles</p>
          </div>
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

      <RouteSelector
        routes={routes}
        activeRouteId={activeRouteId}
        onSelect={handleSelectRoute}
      />

      <div className="h-[55vh] w-full">
        <RouteMap
          stops={stops}
          selectedStopId={selectedStop?.id ?? null}
          onSelectStop={setSelectedStopId}
          userPosition={position}
        />
      </div>

      <ProximityPanel
        stop={selectedStop}
        distance={distance}
        inRange={inRange}
        onVisit={(stopId) => visitMutation.mutate(stopId)}
        isVisiting={visitMutation.isPending}
      />

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
