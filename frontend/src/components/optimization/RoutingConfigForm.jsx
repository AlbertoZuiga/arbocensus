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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const DEFAULTS = {
  minRouteTimeHours: 2,
  maxRouteTimeHours: 3,
  serviceTimeMinutes: 5,
  strategy: "spatial_term",
};

const STRATEGY_OPTIONS = [
  { value: "global", label: "Global" },
  { value: "spatial_term", label: "Término espacial" },
  { value: "cluster_first", label: "Clustering primero" },
  { value: "compare", label: "Comparar las 3" },
];

const hoursToSeconds = (hours) => Math.round(Number(hours) * 3600);
const minutesToSeconds = (minutes) => Math.round(Number(minutes) * 60);

export default function RoutingConfigForm({
  datasetId,
  onJobCreated,
  hasActiveJob = false,
}) {
  const [minRouteTimeHours, setMinRouteTimeHours] = useState(
    DEFAULTS.minRouteTimeHours
  );
  const [maxRouteTimeHours, setMaxRouteTimeHours] = useState(
    DEFAULTS.maxRouteTimeHours
  );
  const [serviceTimeMinutes, setServiceTimeMinutes] = useState(
    DEFAULTS.serviceTimeMinutes
  );
  const [strategy, setStrategy] = useState(DEFAULTS.strategy);

  const hasEmptyField = [
    minRouteTimeHours,
    maxRouteTimeHours,
    serviceTimeMinutes,
  ].some((value) => value === "" || Number.isNaN(Number(value)));

  const { data: fleetEstimate } = useQuery({
    queryKey: [
      "fleet-estimate",
      datasetId,
      minRouteTimeHours,
      serviceTimeMinutes,
    ],
    queryFn: () =>
      fetchFleetEstimate(
        datasetId,
        hoursToSeconds(minRouteTimeHours),
        minutesToSeconds(serviceTimeMinutes),
      ),
    enabled: !!datasetId && !hasEmptyField,
    refetchInterval: false,
    staleTime: 5_000,
  });
  const rangeInvalid =
    !hasEmptyField && Number(maxRouteTimeHours) < Number(minRouteTimeHours);

  const mutation = useMutation({
    mutationFn: () =>
      createJob({
        dataset: datasetId,
        minRouteTimeSec: hoursToSeconds(minRouteTimeHours),
        maxRouteTimeSec: hoursToSeconds(maxRouteTimeHours),
        serviceTimeSec: minutesToSeconds(serviceTimeMinutes),
        strategy,
      }),
    onSuccess: (job) => {
      onJobCreated?.(job);
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
          <div className="space-y-2">
            <Label htmlFor="strategy">Estrategia</Label>
            <Select value={strategy} onValueChange={setStrategy}>
              <SelectTrigger id="strategy">
                <SelectValue>
                  {STRATEGY_OPTIONS.find((o) => o.value === strategy)?.label}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {STRATEGY_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
            {mutation.isPending ? "Generando…" : "Generar rutas"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
