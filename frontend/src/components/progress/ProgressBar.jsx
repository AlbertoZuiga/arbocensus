import { STATUS_COLORS, STATUS_LABELS, statusSegments } from "@/lib/progress.js";
import { cn } from "@/lib/utils";

export default function ProgressBar({ totals, className }) {
  const segments = statusSegments(totals);

  return (
    <div
      className={cn(
        "flex h-2 w-full overflow-hidden rounded-full bg-muted",
        className,
      )}
      role="img"
      aria-label={segments
        .map(({ status, count }) => `${STATUS_LABELS[status]}: ${count}`)
        .join(" · ")}
    >
      {segments.map(({ status, percent }) => (
        <div
          key={status}
          style={{ width: `${percent}%`, backgroundColor: STATUS_COLORS[status] }}
        />
      ))}
    </div>
  );
}
