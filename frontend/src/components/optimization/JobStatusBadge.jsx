import { Badge } from "@/components/ui/badge";

const STATUS_CONFIG = {
  queued: { variant: "secondary", label: "En cola" },
  running: { variant: "default", label: "Ejecutando" },
  completed: { variant: "success", label: "Completado" },
  failed: { variant: "destructive", label: "Fallido" },
  error: { variant: "destructive", label: "Error" },
};

export default function JobStatusBadge({ status }) {
  const config = STATUS_CONFIG[status] ?? {
    variant: "outline",
    label: status ?? "Desconocido",
  };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
