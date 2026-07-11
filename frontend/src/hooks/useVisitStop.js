import { useMutation, useQueryClient } from "@tanstack/react-query";
import { visitStop } from "../api/routes.js";

export function useVisitStop(routeId, position) {
  const queryClient = useQueryClient();
  const queryKey = ["route", routeId];

  return useMutation({
    mutationKey: ["visitStop"],
    mutationFn: ({ stopId, status, photo, notes }) =>
      visitStop(stopId, {
        ...(position ? { lat: position.lat, lon: position.lon } : {}),
        status,
        photo,
        notes,
      }),
    onMutate: async ({ stopId }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          stops: old.stops.map((stop) =>
            stop.id === stopId
              ? { ...stop, visited: true, visited_at: new Date().toISOString() }
              : stop
          ),
        };
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}
