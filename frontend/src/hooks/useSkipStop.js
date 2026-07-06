import { useMutation, useQueryClient } from "@tanstack/react-query";
import { skipStop } from "../api/routes.js";

export function useSkipStop(routeId) {
  const queryClient = useQueryClient();
  const queryKey = ["route", routeId];

  return useMutation({
    mutationKey: ["skipStop"],
    mutationFn: ({ stopId, reason }) => skipStop(stopId, reason),
    onMutate: async ({ stopId, reason }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          stops: old.stops.map((stop) =>
            stop.id === stopId
              ? { ...stop, status: "skipped", skip_reason: reason }
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
