import { QueryClient, defaultShouldDehydrateQuery } from "@tanstack/react-query";
import {
  SKIP_STOP_MUTATION_KEY,
  VISIT_STOP_MUTATION_KEY,
  skipStopMutationFn,
  visitStopMutationFn,
} from "../hooks/observationMutations.js";

export const DAY_MS = 1000 * 60 * 60 * 24;

export const PERSIST_KEY = "arbocensus.query-cache";

export function createAppQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: DAY_MS,
        staleTime: 1000 * 30,
      },
    },
  });

  // Resumed mutations lose the hook that created them: the defaults must
  // rebuild exactly the same request from the persisted variables, and refetch
  // the route so a rejected observation drops its persisted optimistic update.
  const invalidateRoutes = () => {
    queryClient.invalidateQueries({ queryKey: ["route"] });
    queryClient.invalidateQueries({ queryKey: ["my-route"] });
  };

  queryClient.setMutationDefaults(VISIT_STOP_MUTATION_KEY, {
    mutationFn: visitStopMutationFn,
    onSettled: invalidateRoutes,
  });
  queryClient.setMutationDefaults(SKIP_STOP_MUTATION_KEY, {
    mutationFn: skipStopMutationFn,
    onSettled: invalidateRoutes,
  });

  return queryClient;
}

export const dehydrateOptions = {
  shouldDehydrateQuery: (query) =>
    defaultShouldDehydrateQuery(query) && query.queryKey[0] !== "me",
};
