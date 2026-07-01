import client from "./client.js";

export async function createJob({
  dataset,
  minRouteTimeSec,
  maxRouteTimeSec,
  serviceTimeSec,
}) {
  const { data } = await client.post("/optimization/jobs/", {
    dataset,
    min_route_time_sec: minRouteTimeSec,
    max_route_time_sec: maxRouteTimeSec,
    service_time_sec: serviceTimeSec,
  });
  return data;
}

export async function fetchJob(jobId) {
  const { data } = await client.get(`/optimization/jobs/${jobId}/`);
  return data;
}

export async function fetchJobs(datasetId) {
  const { data } = await client.get("/optimization/jobs/", {
    params: { dataset: datasetId },
  });
  return data.results ?? [];
}

export async function fetchSolution(solutionId) {
  const { data } = await client.get(`/optimization/solutions/${solutionId}/`);
  return data;
}
