import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const SANTIAGO = [-33.45, -70.65];
const FIT_MAX_ZOOM = 17;

function FitBounds({ bounds, fitKey }) {
  const map = useMap();
  // Polling maps refetch the same points with a new array identity; refitting on
  // identity would reset the pan/zoom the user set while watching progress.
  const signature = bounds.map((point) => point.join(",")).join(";");
  const latest = useRef(bounds);
  latest.current = bounds;

  useEffect(() => {
    map.fitBounds(latest.current, {
      padding: [40, 40],
      maxZoom: FIT_MAX_ZOOM,
    });
  }, [map, signature, fitKey]);

  return null;
}

export default function BaseMap({
  center = SANTIAGO,
  zoom = 13,
  bounds,
  fitKey,
  className = "h-full w-full",
  preferCanvas = false,
  children,
}) {
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      className={className}
      preferCanvas={preferCanvas}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap"
      />
      {bounds && bounds.length > 0 && (
        <FitBounds bounds={bounds} fitKey={fitKey} />
      )}
      {children}
    </MapContainer>
  );
}
