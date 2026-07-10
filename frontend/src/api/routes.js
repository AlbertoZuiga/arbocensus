import client from "./client.js";

export async function fetchMyRoutes() {
  const { data } = await client.get("/routes/my-route/");
  return data;
}

export async function fetchRouteDetail(routeId) {
  const { data } = await client.get(`/routes/${routeId}/`);
  return data;
}

export async function visitStop(stopId, coords) {
  const { data } = await client.post(`/routes/stops/${stopId}/visit/`, coords ?? {});
  return data;
}

export async function skipStop(stopId, reason) {
  const { data } = await client.post(`/routes/stops/${stopId}/skip/`, { reason });
  return data;
}

export async function fetchRoutePath(routeId) {
  const { data } = await client.get(`/routes/${routeId}/path/`);
  return data;
}

export async function fetchRoutesGeojson(solutionId) {
  const { data } = await client.get("/routes/geojson/", {
    params: { solution_id: solutionId },
  });
  return data;
}

export async function fetchRoutes(solutionId) {
  const { data } = await client.get("/routes/", {
    params: solutionId ? { solution_id: solutionId } : undefined,
  });
  return data.results ?? data;
}

export async function assignRoute(routeId, surveyorId) {
  const { data } = await client.patch(`/routes/${routeId}/assign/`, {
    surveyor_id: surveyorId,
  });
  return data;
}
