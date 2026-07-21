import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { Polyline, Marker, useMap } from "react-leaflet";
import { LocateFixed } from "lucide-react";
import "leaflet/dist/leaflet.css";
import { cn } from "@/lib/utils";
import BaseMap from "../map/BaseMap.jsx";

function stopIcon(sequence, visited, selected) {
  const color = visited ? "#16a34a" : selected ? "#2563eb" : "#475569";
  const size = selected ? 34 : 28;
  return L.divIcon({
    className: "",
    html: `<div style="background:${color};color:#fff;border-radius:9999px;width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.5)">${sequence}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

const userIcon = L.divIcon({
  className: "",
  html: `<div style="background:#0ea5e9;width:18px;height:18px;border-radius:9999px;border:3px solid #fff;box-shadow:0 0 0 5px rgba(14,165,233,.35)"></div>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

function geometryToPositions(geometry) {
  const coordinates = geometry?.coordinates ?? [];
  // GeoJSON coordinates are [lon, lat]; Leaflet expects [lat, lon].
  return coordinates.map(([lon, lat]) => [lat, lon]);
}

function FollowUser({ position, following, onDragStart }) {
  const map = useMap();
  const hasCentered = useRef(false);

  useEffect(() => {
    map.on("dragstart", onDragStart);
    return () => map.off("dragstart", onDragStart);
  }, [map, onDragStart]);

  useEffect(() => {
    if (!following || !position) return;
    if (!hasCentered.current) {
      map.setView([position.lat, position.lon], 17);
      hasCentered.current = true;
    } else {
      map.panTo([position.lat, position.lon], { animate: true });
    }
  }, [map, position, following]);
  return null;
}

function FollowControl({ position, following, onToggle }) {
  const map = useMap();
  const containerRef = useRef(null);
  const active = following && !!position;
  const label = active ? "Dejar de seguir mi ubicación" : "Centrar en mi ubicación";

  useEffect(() => {
    if (containerRef.current) {
      L.DomEvent.disableClickPropagation(containerRef.current);
      L.DomEvent.disableScrollPropagation(containerRef.current);
    }
  }, []);

  const handleClick = () => {
    if (!following && position) {
      map.setView([position.lat, position.lon], Math.max(map.getZoom(), 17));
    }
    onToggle(!following);
  };

  return (
    <div ref={containerRef} className="leaflet-bottom leaflet-right">
      <div className="leaflet-control">
        <button
          type="button"
          onClick={handleClick}
          disabled={!position}
          aria-pressed={active}
          aria-label={label}
          title={label}
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-full border shadow-md",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:opacity-50",
            active
              ? "border-sky-500 bg-sky-500 text-white"
              : "border-slate-200 bg-white text-slate-700",
          )}
        >
          <LocateFixed className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

export default function RouteMap({
  stops,
  selectedStopId,
  onSelectStop,
  userPosition,
  geometry,
}) {
  const stopLine = useMemo(() => stops.map((stop) => [stop.lat, stop.lon]), [stops]);
  const walkedLine = useMemo(() => geometryToPositions(geometry), [geometry]);
  const line = walkedLine.length > 1 ? walkedLine : stopLine;
  const center = stopLine[0] ?? [-33.45, -70.65];
  const [following, setFollowing] = useState(true);
  const stopFollowing = useCallback(() => setFollowing(false), []);

  return (
    <BaseMap center={center} zoom={15} bounds={stopLine}>
      <FollowUser
        position={userPosition}
        following={following}
        onDragStart={stopFollowing}
      />
      <FollowControl
        position={userPosition}
        following={following}
        onToggle={setFollowing}
      />
      {line.length > 1 && (
        <Polyline positions={line} color="#2563eb" weight={5} opacity={0.75} />
      )}
      {stops.map((stop) => (
        <Marker
          key={stop.id}
          position={[stop.lat, stop.lon]}
          icon={stopIcon(
            stop.sequence,
            stop.status === "visited",
            stop.id === selectedStopId,
          )}
          eventHandlers={{ click: () => onSelectStop(stop.id) }}
        />
      ))}
      {userPosition && (
        <Marker position={[userPosition.lat, userPosition.lon]} icon={userIcon} />
      )}
    </BaseMap>
  );
}
