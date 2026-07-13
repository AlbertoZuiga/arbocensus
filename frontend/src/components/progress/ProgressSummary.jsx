import {
  STATUS_COLORS,
  STATUS_LABELS,
  STATUS_ORDER,
  progressPercent,
  resolvedCount,
} from "@/lib/progress.js";
import { Card, CardContent } from "@/components/ui/card";
import ProgressBar from "./ProgressBar.jsx";

export default function ProgressSummary({ totals }) {
  const percent = progressPercent(totals);

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Avance del censo</p>
            <p className="text-3xl font-semibold">{percent}%</p>
          </div>
          <p className="text-sm text-muted-foreground">
            {resolvedCount(totals)} de {totals.total} árboles
          </p>
        </div>

        <ProgressBar totals={totals} />

        <div className="flex flex-wrap gap-4">
          {STATUS_ORDER.map((status) => (
            <span key={status} className="flex items-center gap-2 text-sm">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: STATUS_COLORS[status] }}
              />
              <span className="text-muted-foreground">
                {STATUS_LABELS[status]}
              </span>
              <span className="font-medium">{totals[status]}</span>
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
