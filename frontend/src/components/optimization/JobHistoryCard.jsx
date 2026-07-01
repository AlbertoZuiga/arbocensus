import { useOptimizationJobs } from "@/hooks/useOptimizationJobs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import JobHistoryList from "./JobHistoryList";

export default function JobHistoryCard({ datasetId }) {
  const { data: jobs = [] } = useOptimizationJobs(datasetId);

  if (jobs.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Historial de trabajos</CardTitle>
      </CardHeader>
      <CardContent>
        <JobHistoryList datasetId={datasetId} jobs={jobs} />
      </CardContent>
    </Card>
  );
}
