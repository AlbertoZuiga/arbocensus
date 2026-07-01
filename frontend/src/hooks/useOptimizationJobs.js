import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/optimization.js";

const ACTIVE_STATUSES = ["queued", "running"];

export function useOptimizationJobs(datasetId) {
  return useQuery({
    queryKey: ["optimization-jobs", datasetId],
    queryFn: () => fetchJobs(datasetId),
    enabled: !!datasetId,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((j) => ACTIVE_STATUSES.includes(j.status))
        ? 3000
        : false,
  });
}
