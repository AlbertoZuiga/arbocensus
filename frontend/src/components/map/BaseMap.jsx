import { useEffect } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const SANTIAGO = [-33.45, -70.65];

function FitBounds({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40] });
    }
  }, [map, bounds]);
  return null;
}

export default function BaseMap({
  center = SANTIAGO,
  zoom = 13,
  bounds,
  className = "h-full w-full",
  children,
}) {
  return (
    <MapContainer center={center} zoom={zoom} className={className}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap"
      />
      {bounds && bounds.length > 0 && <FitBounds bounds={bounds} />}
      {children}
    </MapContainer>
  );
}
