import { useEffect } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, Polyline, Marker, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function stopIcon(sequence, visited, selected) {
  const color = visited ? "#16a34a" : selected ? "#2563eb" : "#475569";
  return L.divIcon({
    className: "",
    html: `<div style="background:${color};color:#fff;border-radius:9999px;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)">${sequence}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

const userIcon = L.divIcon({
  className: "",
  html: `<div style="background:#0ea5e9;width:16px;height:16px;border-radius:9999px;border:3px solid #fff;box-shadow:0 0 0 4px rgba(14,165,233,.3)"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function FitBounds({ positions }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 0) {
      map.fitBounds(positions, { padding: [40, 40] });
    }
  }, [map, positions]);
  return null;
}

export default function RouteMap({ stops, selectedStopId, onSelectStop, userPosition }) {
  const line = stops.map((stop) => [stop.lat, stop.lon]);
  const center = line[0] ?? [-33.45, -70.65];

  return (
    <MapContainer center={center} zoom={15} className="h-full w-full">
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap"
      />
      <FitBounds positions={line} />
      {line.length > 1 && (
        <Polyline positions={line} color="#2563eb" weight={4} opacity={0.7} />
      )}
      {stops.map((stop) => (
        <Marker
          key={stop.id}
          position={[stop.lat, stop.lon]}
          icon={stopIcon(stop.sequence, stop.visited, stop.id === selectedStopId)}
          eventHandlers={{ click: () => onSelectStop(stop.id) }}
        />
      ))}
      {userPosition && (
        <Marker position={[userPosition.lat, userPosition.lon]} icon={userIcon} />
      )}
    </MapContainer>
  );
}
