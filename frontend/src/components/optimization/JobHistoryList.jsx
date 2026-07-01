import { Link } from "react-router-dom";

import { formatTimestamp, strategySummary } from "@/lib/optimization";
import JobStatusBadge from "./JobStatusBadge";

export default function JobHistoryList({ datasetId, jobs }) {
  if (!jobs || jobs.length === 0) return null;

  return (
    <ul className="flex flex-col gap-2">
      {jobs.map((job) => (
        <li key={job.id}>
          <Link
            to={`/admin/datasets/${datasetId}/jobs/${job.id}`}
            className="block w-full rounded-md border p-3 text-left transition-colors hover:bg-accent/50"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">
                {formatTimestamp(job.started_at, "short")}
              </span>
              <JobStatusBadge status={job.status} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {strategySummary(job)}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
