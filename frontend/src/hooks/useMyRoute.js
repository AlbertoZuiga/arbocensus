import { useQuery } from "@tanstack/react-query";
import { fetchMyRoutes, fetchRouteDetail, fetchRoutePath } from "../api/routes.js";

export const EMPTY_ROUTES_POLL_MS = 30_000;

export function myRouteRefetchInterval(query) {
  const routes = query.state.data;
  return Array.isArray(routes) && routes.length === 0
    ? EMPTY_ROUTES_POLL_MS
    : false;
}

export function useMyRoute() {
  return useQuery({
    queryKey: ["my-route"],
    queryFn: fetchMyRoutes,
    refetchInterval: myRouteRefetchInterval,
  });
}

export function useRouteDetail(routeId) {
  return useQuery({
    queryKey: ["route", routeId],
    queryFn: () => fetchRouteDetail(routeId),
    enabled: !!routeId,
  });
}

export function useRoutePath(routeId) {
  return useQuery({
    queryKey: ["route-path", routeId],
    queryFn: () => fetchRoutePath(routeId),
    enabled: !!routeId,
    retry: false,
  });
}
