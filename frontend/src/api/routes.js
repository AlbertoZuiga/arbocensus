import client from "./client.js";

export async function fetchMyRoutes() {
  const { data } = await client.get("/routes/my-route/");
  return data;
}

export async function fetchRouteDetail(routeId) {
  const { data } = await client.get(`/routes/${routeId}/`);
  return data;
}

export async function visitStop(stopId) {
  const { data } = await client.post(`/routes/stops/${stopId}/visit/`);
  return data;
}

export async function fetchRoutesGeojson(solutionId) {
  const { data } = await client.get("/routes/geojson/", {
    params: { solution_id: solutionId },
  });
  return data;
}
