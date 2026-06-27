import { useQuery } from "@tanstack/react-query";
import { fetchMyRoutes, fetchRouteDetail } from "../api/routes.js";

export function useMyRoute() {
  return useQuery({
    queryKey: ["my-route"],
    queryFn: fetchMyRoutes,
  });
}

export function useRouteDetail(routeId) {
  return useQuery({
    queryKey: ["route", routeId],
    queryFn: () => fetchRouteDetail(routeId),
    enabled: !!routeId,
  });
}
