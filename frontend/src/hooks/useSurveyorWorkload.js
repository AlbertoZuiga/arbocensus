import { useQuery } from "@tanstack/react-query";
import { fetchWorkload } from "../api/routes.js";

export function useSurveyorWorkload({ enabled = true } = {}) {
  return useQuery({
    queryKey: ["surveyor-workload"],
    queryFn: fetchWorkload,
    enabled,
    staleTime: 0,
  });
}
