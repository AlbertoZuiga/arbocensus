import { useQuery } from "@tanstack/react-query";
import { fetchJob } from "../api/optimization.js";
import { pollInterval } from "../lib/optimization.js";

export function useOptimizationJob(jobId) {
  return useQuery({
    queryKey: ["optimization-job", jobId],
    queryFn: () => fetchJob(jobId),
    enabled: !!jobId,
    refetchInterval: (query) =>
      pollInterval(query.state.data?.status, query.state.data?.created_at),
  });
}
