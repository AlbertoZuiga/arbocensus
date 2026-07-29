import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useOptimizationJobs } from "@/hooks/useOptimizationJobs";
import { formatTimestamp } from "@/lib/optimization";
import { getErrorMessage } from "@/lib/errors";
import { Alert, AlertDescription } from "@/components/ui/alert";
import RoutingConfigForm from "./RoutingConfigForm";
import SolutionCandidatesList from "./SolutionCandidatesList";

function sweepStatusText(sweepJobs) {
  if (sweepJobs.some((job) => job.status === "failed")) {
    return "Una de las configuraciones falló; puede faltar una solución.";
  }
  const done = sweepJobs.filter((job) => job.status === "completed").length;
  if (done === sweepJobs.length) return null;
  return `Optimizando… ${done} de ${sweepJobs.length} configuraciones listas.`;
}

export default function OptimizationPanel({
  datasetId,
  activeSolutionId = null,
  onViewSolution,
}) {
  const queryClient = useQueryClient();
  const [viewedConfig, setViewedConfig] = useState(null);

  const { data: jobs = [], error } = useOptimizationJobs(datasetId);

  // jobs are newest-first; the newest job's config is the sweep in progress
  // (or most recently finished), which may span several jobs (one per preset).
  const latestConfig = jobs[0]?.config;
  const currentSweep = jobs.filter((job) => job.config === latestConfig);
  const hasActiveJob = jobs.some((job) =>
    ["queued", "running"].includes(job.status)
  );
  const sweepStatus = latestConfig ? sweepStatusText(currentSweep) : null;

  // One entry per past sweep (RoutingConfig), newest first, for the sweep
  // switcher inside the candidate list.
  const sweeps = useMemo(() => {
    const seen = new Set();
    const list = [];
    for (const job of jobs) {
      if (seen.has(job.config)) continue;
      seen.add(job.config);
      list.push({ config: job.config, label: formatTimestamp(job.created_at, "short") });
    }
    return list;
  }, [jobs]);

  const handleJobCreated = () => {
    queryClient.invalidateQueries({
      queryKey: ["optimization-jobs", datasetId],
    });
    setViewedConfig(null);
  };

  return (
    <div className="flex flex-col gap-4">
      <RoutingConfigForm
        datasetId={datasetId}
        onJobCreated={handleJobCreated}
        hasActiveJob={hasActiveJob}
      />

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(error, "No se pudieron cargar los trabajos.")}
          </AlertDescription>
        </Alert>
      )}

      {sweepStatus && (
        <p className="text-sm text-muted-foreground">{sweepStatus}</p>
      )}

      <SolutionCandidatesList
        datasetId={datasetId}
        hasActiveJob={hasActiveJob}
        viewedConfig={viewedConfig ?? latestConfig}
        sweeps={sweeps}
        onChangeViewedConfig={setViewedConfig}
        activeSolutionId={activeSolutionId}
        onViewSolution={onViewSolution}
      />
    </div>
  );
}
