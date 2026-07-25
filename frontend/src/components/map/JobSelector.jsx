import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import JobStatusBadge from "@/components/optimization/JobStatusBadge.jsx";
import { formatTimestamp } from "@/lib/optimization";

export default function JobSelector({ jobs, value, onChange }) {
  if (jobs.length === 0) return null;

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        aria-label="Optimización"
        className="w-auto gap-2 border bg-background/90 shadow-md backdrop-blur"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {jobs.map((job) => (
          <SelectItem key={job.id} value={job.id}>
            <span className="flex items-center gap-2">
              {formatTimestamp(job.started_at, "short")}
              <JobStatusBadge status={job.status} />
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
