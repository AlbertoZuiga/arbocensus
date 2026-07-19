export function routeOptionLabel(route, index) {
  const resolved = (route.visited_count ?? 0) + (route.skipped_count ?? 0);
  return `Ruta ${index + 1} · ${resolved}/${route.total_trees}`;
}
