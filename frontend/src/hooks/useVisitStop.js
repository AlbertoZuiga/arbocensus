import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  VISIT_STOP_MUTATION_KEY,
  visitStopMutationFn,
  withCapturePosition,
} from "./observationMutations.js";

export function useVisitStop(routeId, position) {
  const queryClient = useQueryClient();
  const queryKey = ["route", routeId];

  const mutation = useMutation({
    mutationKey: VISIT_STOP_MUTATION_KEY,
    mutationFn: visitStopMutationFn,
    onMutate: async ({ stopId }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          stops: old.stops.map((stop) =>
            stop.id === stopId
              ? {
                  ...stop,
                  status: "visited",
                  visited_at: new Date().toISOString(),
                }
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
      queryClient.invalidateQueries({ queryKey: ["my-route"] });
    },
  });

  const { mutate, mutateAsync } = mutation;

  return {
    ...mutation,
    mutate: useCallback(
      (variables, options) =>
        mutate(withCapturePosition(variables, position), options),
      [mutate, position]
    ),
    mutateAsync: useCallback(
      (variables, options) =>
        mutateAsync(withCapturePosition(variables, position), options),
      [mutateAsync, position]
    ),
  };
}
