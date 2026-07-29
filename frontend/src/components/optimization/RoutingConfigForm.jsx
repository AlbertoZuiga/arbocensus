import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { createJob, fetchFleetEstimate } from "@/api/optimization";
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
  minRouteTimeMinutes: 120,
  maxRouteTimeMinutes: 180,
  serviceTimeMinutes: 2,
};

const minutesToSeconds = (minutes) => Math.round(Number(minutes) * 60);

export default function RoutingConfigForm({
  datasetId,
  onJobCreated,
  hasActiveJob = false,
}) {
  const [minRouteTimeMinutes, setMinRouteTimeMinutes] = useState(
    DEFAULTS.minRouteTimeMinutes
  );
  const [maxRouteTimeMinutes, setMaxRouteTimeMinutes] = useState(
    DEFAULTS.maxRouteTimeMinutes
  );
  const [serviceTimeMinutes, setServiceTimeMinutes] = useState(
    DEFAULTS.serviceTimeMinutes
  );

  const hasEmptyField = [
    minRouteTimeMinutes,
    maxRouteTimeMinutes,
    serviceTimeMinutes,
  ].some((value) => value === "" || Number.isNaN(Number(value)));

  const { data: fleetEstimate } = useQuery({
    queryKey: [
      "fleet-estimate",
      datasetId,
      minRouteTimeMinutes,
      serviceTimeMinutes,
    ],
    queryFn: () =>
      fetchFleetEstimate(
        datasetId,
        minutesToSeconds(minRouteTimeMinutes),
        minutesToSeconds(serviceTimeMinutes),
      ),
    enabled: !!datasetId && !hasEmptyField,
    refetchInterval: false,
    staleTime: 5_000,
  });
  const rangeInvalid =
    !hasEmptyField && Number(maxRouteTimeMinutes) < Number(minRouteTimeMinutes);

  const mutation = useMutation({
    mutationFn: () =>
      createJob({
        dataset: datasetId,
        minRouteTimeSec: minutesToSeconds(minRouteTimeMinutes),
        maxRouteTimeSec: minutesToSeconds(maxRouteTimeMinutes),
        serviceTimeSec: minutesToSeconds(serviceTimeMinutes),
      }),
    onSuccess: (jobs) => {
      onJobCreated?.(jobs);
    },
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    if (hasEmptyField || rangeInvalid || hasActiveJob) return;
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
            <Label htmlFor="min-route-time">Tiempo mínimo por ruta (min)</Label>
            <Input
              id="min-route-time"
              type="number"
              min="0"
              step="5"
              value={minRouteTimeMinutes}
              onChange={(e) => setMinRouteTimeMinutes(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              El optimizador evita rutas más cortas que esto.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="max-route-time">Tiempo máximo por ruta (min)</Label>
            <Input
              id="max-route-time"
              type="number"
              min="0"
              step="5"
              value={maxRouteTimeMinutes}
              onChange={(e) => setMaxRouteTimeMinutes(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Ninguna ruta puede superar este tope.
            </p>
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

          {fleetEstimate != null && (
            <p className="text-sm text-muted-foreground">
              Hasta {fleetEstimate} rutas aprox.
            </p>
          )}

          {hasActiveJob && (
            <p className="text-sm text-muted-foreground">
              Ya hay una optimización en curso para este dataset.
            </p>
          )}

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

          <Button
            type="submit"
            disabled={
              mutation.isPending || hasEmptyField || rangeInvalid || hasActiveJob
            }
          >
            {mutation.isPending ? "Generando…" : "Generar y comparar rutas"}
          </Button>
          <p className="text-xs text-muted-foreground">
            Corre 3 configuraciones × 3 estrategias y recomienda la mejor.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
