export function isStopLocked(stop, nextPendingStopId) {
  return !stop.visited && nextPendingStopId != null && stop.id !== nextPendingStopId;
}
