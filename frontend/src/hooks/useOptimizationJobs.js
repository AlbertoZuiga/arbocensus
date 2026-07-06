import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/optimization.js";
import { pollInterval } from "../lib/optimization.js";

export function useOptimizationJobs(datasetId) {
  return useQuery({
    queryKey: ["optimization-jobs", datasetId],
    queryFn: () => fetchJobs(datasetId),
    enabled: !!datasetId,
    refetchInterval: (query) =>
      (query.state.data ?? []).some(
        (j) => pollInterval(j.status, j.created_at) !== false,
      )
        ? 3000
        : false,
  });
}
