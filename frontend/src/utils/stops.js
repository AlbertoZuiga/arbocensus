export function isStopResolved(stop) {
  return stop.visited || stop.status === "skipped";
}

export function isStopLocked(stop, nextPendingStopId) {
  return (
    !isStopResolved(stop) &&
    nextPendingStopId != null &&
    stop.id !== nextPendingStopId
  );
}
