export const ROUTE_COLORS = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#65a30d",
  "#ea580c",
  "#0d9488",
];

export function geojsonToRoutes(featureCollection) {
  const features = featureCollection?.features ?? [];
  return features.map((feature, index) => {
    // GeoJSON LineString coordinates are [lon, lat]; Leaflet expects [lat, lon].
    const positions = (feature.geometry?.coordinates ?? []).map(
      ([lon, lat]) => [lat, lon],
    );
    const props = feature.properties ?? {};
    return {
      routeNumber: props.route_number,
      totalTrees: props.total_trees,
      travelTimeSec: props.travel_time_sec,
      color: ROUTE_COLORS[index % ROUTE_COLORS.length],
      positions,
    };
  });
}
