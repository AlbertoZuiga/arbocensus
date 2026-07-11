import { useMemo, useState } from "react";
import { useMyRoute, useRouteDetail, useRoutePath } from "../../hooks/useMyRoute.js";
import { useWatchPosition } from "../../hooks/useWatchPosition.js";
import { useVisitStop } from "../../hooks/useVisitStop.js";
import { useSkipStop } from "../../hooks/useSkipStop.js";
import { useWakeLock } from "../../hooks/useWakeLock.js";
import RouteMap from "../../components/surveyor/RouteMap.jsx";
import StopList from "../../components/surveyor/StopList.jsx";
import ProximityPanel from "../../components/surveyor/ProximityPanel.jsx";
import SurveyorHeader from "../../components/surveyor/SurveyorHeader.jsx";
import { haversineMeters, PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";
import { isStopLocked, isStopResolved } from "../../utils/stops.js";

function CenteredMessage({ children }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-center">
      <p className="text-muted-foreground">{children}</p>
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
  const routePath = useRoutePath(activeRouteId);
  const { position } = useWatchPosition();
  const visitMutation = useVisitStop(activeRouteId, position);
  const skipMutation = useSkipStop(activeRouteId);
  useWakeLock();
  const [selectedStopId, setSelectedStopId] = useState(null);

  const stops = useMemo(() => routeDetail.data?.stops ?? [], [routeDetail.data]);

  const nextPendingStop = useMemo(
    () => stops.find((stop) => !isStopResolved(stop)) ?? null,
    [stops]
  );

  const selectedStop = useMemo(() => {
    if (selectedStopId) {
      return stops.find((stop) => stop.id === selectedStopId) ?? null;
    }
    return nextPendingStop ?? stops[0] ?? null;
  }, [stops, selectedStopId, nextPendingStop]);

  const selectedStopLocked =
    selectedStop != null && isStopLocked(selectedStop, nextPendingStop?.id ?? null);

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

  const resolvedCount = stops.filter((stop) => isStopResolved(stop)).length;

  const handleSelectRoute = (routeId) => {
    visitMutation.reset();
    skipMutation.reset();
    setSelectedRouteId(routeId);
    setSelectedStopId(null);
  };

  const handleSelectStop = (stopId) => {
    visitMutation.reset();
    skipMutation.reset();
    setSelectedStopId(stopId);
  };

  return (
    <main className="flex h-dvh flex-col overflow-hidden bg-slate-50">
      <SurveyorHeader
        routes={routes}
        activeRouteId={activeRouteId}
        activeIndex={activeIndex}
        onSelectRoute={handleSelectRoute}
        stopsCount={stops.length}
        resolvedCount={resolvedCount}
        position={position}
      />

      <div className="h-[42dvh] min-h-[200px] w-full shrink-0">
        <RouteMap
          stops={stops}
          selectedStopId={selectedStop?.id ?? null}
          onSelectStop={handleSelectStop}
          userPosition={position}
          geometry={routePath.data}
        />
      </div>

      <ProximityPanel
        stop={selectedStop}
        distance={distance}
        inRange={inRange}
        locked={selectedStopLocked}
        onVisit={(stopId, payload) => {
          skipMutation.reset();
          visitMutation.mutate(
            { stopId, ...payload },
            { onSuccess: () => setSelectedStopId(null) }
          );
        }}
        onSkip={(stopId, payload) => {
          visitMutation.reset();
          skipMutation.mutate(
            { stopId, ...payload },
            { onSuccess: () => setSelectedStopId(null) }
          );
        }}
        isVisiting={visitMutation.isPending}
        isSkipping={skipMutation.isPending}
        visitError={visitMutation.isError ? visitMutation.error : null}
        skipError={skipMutation.isError ? skipMutation.error : null}
      />

      <section className="pb-safe flex-1 overflow-y-auto" aria-label="Lista de árboles">
        <StopList
          stops={stops}
          selectedStopId={selectedStop?.id ?? null}
          nextPendingStopId={nextPendingStop?.id ?? null}
          onSelectStop={handleSelectStop}
        />
      </section>
    </main>
  );
}
