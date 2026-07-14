import client from "./client.js";

export async function fetchCensusProgress(datasetId) {
  const { data } = await client.get("/routes/progress/", {
    params: { dataset: datasetId },
  });
  return data;
}

export async function fetchCensusProgressStops(datasetId) {
  const { data } = await client.get("/routes/progress-geojson/", {
    params: { dataset: datasetId },
  });
  return data;
}
