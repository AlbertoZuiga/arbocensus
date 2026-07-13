import { useQuery } from "@tanstack/react-query";

import {
  fetchCensusProgress,
  fetchCensusProgressStops,
} from "../api/progress.js";
import { fetchRoutesGeojson } from "../api/routes.js";
import { progressPollInterval, stopsPollInterval } from "../lib/progress.js";

export function useCensusProgress(datasetId) {
  return useQuery({
    queryKey: ["census-progress", datasetId],
    queryFn: () => fetchCensusProgress(datasetId),
    enabled: !!datasetId,
    refetchInterval: progressPollInterval,
  });
}

export function useCensusProgressStops(datasetId, { enabled = false, live = false }) {
  return useQuery({
    queryKey: ["census-progress-stops", datasetId],
    queryFn: () => fetchCensusProgressStops(datasetId),
    enabled: enabled && !!datasetId,
    refetchInterval: (query) => stopsPollInterval(query, live),
  });
}

export function useRouteLines(solutionId, enabled = false) {
  return useQuery({
    queryKey: ["routes-geojson", solutionId],
    queryFn: () => fetchRoutesGeojson(solutionId),
    enabled: enabled && !!solutionId,
    staleTime: Infinity,
  });
}
