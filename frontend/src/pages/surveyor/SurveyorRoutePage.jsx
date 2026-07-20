import { useMemo, useState } from "react";
import { ClipboardList, RefreshCw, TreePine } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  EMPTY_ROUTES_POLL_MS,
  useMyRoute,
  useRouteDetail,
  useRoutePath,
} from "../../hooks/useMyRoute.js";
import { useWatchPosition } from "../../hooks/useWatchPosition.js";
import { useVisitStop } from "../../hooks/useVisitStop.js";
import { useSkipStop } from "../../hooks/useSkipStop.js";
import { useWakeLock } from "../../hooks/useWakeLock.js";
import RouteMap from "../../components/surveyor/RouteMap.jsx";
import StopList from "../../components/surveyor/StopList.jsx";
import ProximityPanel from "../../components/surveyor/ProximityPanel.jsx";
import SurveyorHeader from "../../components/surveyor/SurveyorHeader.jsx";
import PendingQueueIndicator from "../../components/surveyor/PendingQueueIndicator.jsx";
import UserMenu from "../../components/UserMenu.jsx";
import RouteCompletionScreen from "../../components/surveyor/RouteCompletionScreen.jsx";
import { haversineMeters, PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";
import { isStopLocked, isStopResolved } from "../../utils/stops.js";

function MinimalHeader() {
  return (
    <header className="pt-safe sticky top-0 z-[1000] border-b bg-white shadow-sm">
      <div className="flex items-center justify-between gap-2 px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <TreePine className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
          <span className="truncate text-base font-extrabold tracking-tight text-slate-900">
            Arbocensus
          </span>
        </div>
        <UserMenu />
      </div>
    </header>
  );
}

function StatusScreen({ children }) {
  return (
    <main className="flex min-h-screen flex-col bg-slate-50">
      <MinimalHeader />
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
        {children}
      </div>
    </main>
  );
}

export default function SurveyorRoutePage() {
  const myRoute = useMyRoute();
  const routes = useMemo(
    () =>
      [...(myRoute.data ?? [])].sort((a, b) => a.route_number - b.route_number),
    [myRoute.data],
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

  const stops = useMemo(
    () => routeDetail.data?.stops ?? [],
    [routeDetail.data],
  );

  const nextPendingStop = useMemo(
    () => stops.find((stop) => !isStopResolved(stop)) ?? null,
    [stops],
  );

  const selectedStop = useMemo(() => {
    if (selectedStopId) {
      return stops.find((stop) => stop.id === selectedStopId) ?? null;
    }
    return nextPendingStop ?? stops[0] ?? null;
  }, [stops, selectedStopId, nextPendingStop]);

  const selectedStopLocked =
    selectedStop != null &&
    isStopLocked(selectedStop, nextPendingStop?.id ?? null);

  const distance = useMemo(() => {
    if (!position || !selectedStop) return null;
    return haversineMeters(
      position.lat,
      position.lon,
      selectedStop.lat,
      selectedStop.lon,
    );
  }, [position, selectedStop]);

  const inRange = distance != null && distance <= PROXIMITY_THRESHOLD_M;

  if (myRoute.isLoading || (activeRouteId && routeDetail.isLoading)) {
    return (
      <StatusScreen>
        <p className="text-muted-foreground">Cargando ruta…</p>
      </StatusScreen>
    );
  }
  if (myRoute.isError) {
    return (
      <StatusScreen>
        <p className="text-muted-foreground">No se pudo cargar tu ruta.</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => myRoute.refetch()}
          disabled={myRoute.isFetching}
        >
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
          Reintentar
        </Button>
      </StatusScreen>
    );
  }
  if (!activeRouteId) {
    return (
      <StatusScreen>
        <ClipboardList className="h-12 w-12 text-slate-400" aria-hidden="true" />
        <p className="text-lg font-bold text-slate-900">
          Aún no tienes rutas asignadas
        </p>
        <p className="text-sm text-muted-foreground">
          Avisa a tu coordinador para que te asigne una ruta. Esta pantalla se
          actualiza sola cada {EMPTY_ROUTES_POLL_MS / 1000} segundos.
        </p>
        <Button
          type="button"
          variant="outline"
          onClick={() => myRoute.refetch()}
          disabled={myRoute.isFetching}
        >
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
          Actualizar
        </Button>
      </StatusScreen>
    );
  }

  const resolvedCount = stops.filter((stop) => isStopResolved(stop)).length;
  const routeCompleted = stops.length > 0 && resolvedCount === stops.length;

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

      <PendingQueueIndicator />

      {routeCompleted ? (
        <RouteCompletionScreen stops={stops} />
      ) : (
        <>
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
                { onSuccess: () => setSelectedStopId(null) },
              );
            }}
            onSkip={(stopId, payload) => {
              visitMutation.reset();
              skipMutation.mutate(
                { stopId, ...payload },
                { onSuccess: () => setSelectedStopId(null) },
              );
            }}
            isVisiting={visitMutation.isPending}
            isSkipping={skipMutation.isPending}
            visitError={visitMutation.isError ? visitMutation.error : null}
            skipError={skipMutation.isError ? skipMutation.error : null}
          />

          <section
            className="pb-safe flex-1 overflow-y-auto"
            aria-label="Lista de árboles"
          >
            <StopList
              stops={stops}
              selectedStopId={selectedStop?.id ?? null}
              nextPendingStopId={nextPendingStop?.id ?? null}
              onSelectStop={handleSelectStop}
            />
          </section>
        </>
      )}
    </main>
  );
}
