import client from "./client.js";

export async function fetchMyRoutes() {
  const { data } = await client.get("/routes/my-route/");
  return data;
}

export async function fetchRouteDetail(routeId) {
  const { data } = await client.get(`/routes/${routeId}/`);
  return data;
}

function observationBody({ photo, ...fields }) {
  const present = Object.fromEntries(
    Object.entries(fields).filter(([, value]) => value != null)
  );
  if (!photo) return present;
  const form = new FormData();
  Object.entries(present).forEach(([key, value]) => form.append(key, value));
  form.append("photo", photo);
  return form;
}

export async function visitStop(stopId, fields = {}) {
  const { data } = await client.post(
    `/routes/stops/${stopId}/visit/`,
    observationBody(fields)
  );
  return data;
}

export async function skipStop(stopId, fields = {}) {
  const { data } = await client.post(
    `/routes/stops/${stopId}/skip/`,
    observationBody(fields)
  );
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
