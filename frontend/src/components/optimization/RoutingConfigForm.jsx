import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { createJob } from "@/api/optimization";
import { getErrorMessage } from "@/lib/errors";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const DEFAULTS = {
  minRouteTimeHours: 2,
  maxRouteTimeHours: 3,
  serviceTimeMinutes: 5,
};

const hoursToSeconds = (hours) => Math.round(Number(hours) * 3600);
const minutesToSeconds = (minutes) => Math.round(Number(minutes) * 60);

export default function RoutingConfigForm({ datasetId, onJobCreated }) {
  const [minRouteTimeHours, setMinRouteTimeHours] = useState(
    DEFAULTS.minRouteTimeHours
  );
  const [maxRouteTimeHours, setMaxRouteTimeHours] = useState(
    DEFAULTS.maxRouteTimeHours
  );
  const [serviceTimeMinutes, setServiceTimeMinutes] = useState(
    DEFAULTS.serviceTimeMinutes
  );

  const rangeInvalid = Number(maxRouteTimeHours) < Number(minRouteTimeHours);

  const mutation = useMutation({
    mutationFn: () =>
      createJob({
        dataset: datasetId,
        minRouteTimeSec: hoursToSeconds(minRouteTimeHours),
        maxRouteTimeSec: hoursToSeconds(maxRouteTimeHours),
        serviceTimeSec: minutesToSeconds(serviceTimeMinutes),
      }),
    onSuccess: (job) => {
      onJobCreated?.(job);
    },
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    if (rangeInvalid) return;
    mutation.mutate();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuración de rutas</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="min-route-time">Tiempo mínimo por ruta (h)</Label>
            <Input
              id="min-route-time"
              type="number"
              min="0"
              step="0.25"
              value={minRouteTimeHours}
              onChange={(e) => setMinRouteTimeHours(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max-route-time">Tiempo máximo por ruta (h)</Label>
            <Input
              id="max-route-time"
              type="number"
              min="0"
              step="0.25"
              value={maxRouteTimeHours}
              onChange={(e) => setMaxRouteTimeHours(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="service-time">
              Tiempo de censo por árbol (min)
            </Label>
            <Input
              id="service-time"
              type="number"
              min="0"
              step="0.5"
              value={serviceTimeMinutes}
              onChange={(e) => setServiceTimeMinutes(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Tiempo estimado para censar un árbol en terreno.
            </p>
          </div>

          {rangeInvalid && (
            <p className="text-sm text-destructive">
              El tiempo mínimo no puede ser mayor que el máximo.
            </p>
          )}

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {getErrorMessage(
                mutation.error,
                "No se pudo crear el trabajo de optimización"
              )}
            </p>
          )}

          <Button type="submit" disabled={mutation.isPending || rangeInvalid}>
            {mutation.isPending ? "Generando…" : "Generar rutas"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
