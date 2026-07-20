import { visitStop, skipStop } from "../api/routes.js";

export const VISIT_STOP_MUTATION_KEY = ["visitStop"];
export const SKIP_STOP_MUTATION_KEY = ["skipStop"];

export function isObservationMutation(mutation) {
  const [key] = mutation.options.mutationKey ?? [];
  return (
    key === VISIT_STOP_MUTATION_KEY[0] || key === SKIP_STOP_MUTATION_KEY[0]
  );
}

export function visitStopMutationFn({ stopId, lat, lon, status, photo, notes }) {
  return visitStop(stopId, { lat, lon, status, photo, notes });
}

export function skipStopMutationFn({ stopId, reason, status, photo, notes }) {
  return skipStop(stopId, { reason, status, photo, notes });
}

// The surveyor may register a tree far from where the queue drains, so the
// capture position travels inside the mutation variables instead of a closure.
export function withCapturePosition(variables, position) {
  if (!position) return variables;
  return { lat: position.lat, lon: position.lon, ...variables };
}
