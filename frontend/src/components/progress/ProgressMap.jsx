import { useMemo, useState } from "react";
import { CircleMarker, Polyline, Popup } from "react-leaflet";

import { STATUS_COLORS, STATUS_LABELS, STATUS_ORDER } from "@/lib/progress.js";
import { cn } from "@/lib/utils";
import BaseMap from "@/components/map/BaseMap.jsx";
import { geojsonToRoutes } from "@/components/map/routeGeojson.js";

function toStops(featureCollection) {
  const features = featureCollection?.features ?? [];
  return features.map((feature) => {
    const [lon, lat] = feature.geometry.coordinates;
    return {
      id: feature.id,
      position: [lat, lon],
      ...feature.properties,
    };
  });
}

export default function ProgressMap({
  stops: featureCollection,
  routeLines,
  visibleRouteNumbers,
  showRoutes,
  onToggleRoutes,
}) {
  const [hidden, setHidden] = useState([]);

  const allStops = useMemo(
    () => toStops(featureCollection),
    [featureCollection],
  );
  const stops = useMemo(
    () =>
      visibleRouteNumbers
        ? allStops.filter((stop) => visibleRouteNumbers.has(stop.route_number))
        : allStops,
    [allStops, visibleRouteNumbers],
  );
  const visibleStops = stops.filter((stop) => !hidden.includes(stop.status));
  const bounds = useMemo(() => stops.map((stop) => stop.position), [stops]);

  const routes = useMemo(() => geojsonToRoutes(routeLines), [routeLines]);
  const visibleRoutes = useMemo(
    () =>
      visibleRouteNumbers
        ? routes.filter((route) => visibleRouteNumbers.has(route.routeNumber))
        : routes,
    [routes, visibleRouteNumbers],
  );

  const toggleStatus = (status) =>
    setHidden((current) =>
      current.includes(status)
        ? current.filter((s) => s !== status)
        : [...current, status],
    );

  return (
    <div className="relative h-full w-full">
      <BaseMap bounds={bounds} preferCanvas>
        {showRoutes &&
          visibleRoutes.map((route) => (
            <Polyline
              key={route.routeNumber}
              positions={route.positions}
              pathOptions={{ color: route.color, weight: 3, opacity: 0.55 }}
            />
          ))}

        {visibleStops.map((stop) => (
          <CircleMarker
            key={stop.id}
            center={stop.position}
            radius={5}
            pathOptions={{
              color: "#fff",
              weight: 1,
              fillColor: STATUS_COLORS[stop.status],
              fillOpacity: 0.9,
            }}
          >
            <Popup>
              <span className="font-medium">
                Ruta {stop.route_number} · Parada {stop.sequence + 1}
              </span>
              <br />
              {STATUS_LABELS[stop.status]}
              {stop.skip_reason && ` · ${stop.skip_reason}`}
              <br />
              {stop.surveyor_name ?? "Sin asignar"}
            </Popup>
          </CircleMarker>
        ))}
      </BaseMap>

      <button
        type="button"
        aria-pressed={!!showRoutes}
        onClick={onToggleRoutes}
        className={cn(
          "absolute right-3 top-3 z-[1000] rounded-lg border px-3 py-1.5 text-sm shadow-md backdrop-blur",
          showRoutes ? "bg-muted" : "bg-background/90 hover:bg-muted/50",
        )}
      >
        Trazado de rutas
      </button>

      <div className="absolute bottom-3 left-3 z-[1000] flex flex-col gap-1 rounded-lg border bg-background/90 p-2 shadow-md backdrop-blur">
        {STATUS_ORDER.map((status) => {
          const count = stops.filter((stop) => stop.status === status).length;
          const off = hidden.includes(status);
          return (
            <button
              key={status}
              type="button"
              aria-pressed={!off}
              onClick={() => toggleStatus(status)}
              className={cn(
                "flex items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-muted",
                off && "opacity-40",
              )}
            >
              <span
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: STATUS_COLORS[status] }}
              />
              <span>{STATUS_LABELS[status]}</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
