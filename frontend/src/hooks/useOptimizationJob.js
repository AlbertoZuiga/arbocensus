import { useQuery } from "@tanstack/react-query";
import { fetchJob } from "../api/optimization.js";

const ACTIVE_STATUSES = ["queued", "running"];

export function pollInterval(status) {
  return ACTIVE_STATUSES.includes(status) ? 3000 : false;
}

export function useOptimizationJob(jobId) {
  return useQuery({
    queryKey: ["optimization-job", jobId],
    queryFn: () => fetchJob(jobId),
    enabled: !!jobId,
    refetchInterval: (query) => pollInterval(query.state.data?.status),
  });
}
