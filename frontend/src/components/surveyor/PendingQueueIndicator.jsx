import { useMutationState } from "@tanstack/react-query";
import { CloudUpload, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { useOnlineStatus } from "../../hooks/useOnlineStatus.js";
import { isObservationMutation } from "../../hooks/observationMutations.js";

function observationsLabel(count) {
  return count === 1 ? "1 observación" : `${count} observaciones`;
}

export default function PendingQueueIndicator() {
  const online = useOnlineStatus();
  const pendingCount = useMutationState({
    filters: {
      predicate: (mutation) =>
        mutation.state.isPaused && isObservationMutation(mutation),
    },
    select: (mutation) => mutation.mutationId,
  }).length;

  if (online && pendingCount === 0) return null;

  const Icon = online ? CloudUpload : WifiOff;
  const message = online
    ? `Enviando ${observationsLabel(pendingCount)}…`
    : pendingCount > 0
      ? `Sin conexión · ${observationsLabel(pendingCount)} en espera`
      : "Sin conexión · se guardará en el dispositivo";

  return (
    <div
      role="status"
      className={cn(
        "flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-semibold",
        online ? "bg-sky-100 text-sky-900" : "bg-amber-100 text-amber-900"
      )}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
