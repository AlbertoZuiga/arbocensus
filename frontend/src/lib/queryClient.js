import { QueryClient, defaultShouldDehydrateQuery } from "@tanstack/react-query";
import { visitStop } from "../api/routes.js";

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

  queryClient.setMutationDefaults(["visitStop"], {
    mutationFn: (stopId) => visitStop(stopId),
  });

  return queryClient;
}

export const dehydrateOptions = {
  shouldDehydrateQuery: (query) =>
    defaultShouldDehydrateQuery(query) && query.queryKey[0] !== "me",
};
