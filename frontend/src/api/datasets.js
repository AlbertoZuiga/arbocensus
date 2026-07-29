import client from "./client.js";

export async function fetchDatasets() {
  const { data } = await client.get("/datasets/");
  return data.results ?? data;
}

export async function fetchDataset(id) {
  const { data } = await client.get(`/datasets/${id}/`);
  return data;
}

export async function fetchDatasetTrees(id) {
  const { data } = await client.get(`/datasets/${id}/trees/`);
  return data;
}

export async function fetchTreeObservations(treeId) {
  const { data } = await client.get(`/datasets/trees/${treeId}/observations/`);
  return data;
}

export async function fetchLegacyTreeObservations(source, externalId) {
  const { data } = await client.get(
    `/datasets/legacy/trees/${source}/${externalId}/observations/`,
  );
  return data;
}

export async function fetchLegacyAreas() {
  const { data } = await client.get("/datasets/legacy/areas/");
  return data;
}

export async function fetchLegacyTrees() {
  const { data } = await client.get("/datasets/legacy/trees/");
  return data;
}

export async function createDatasetFromLegacySelection({ name, trees }) {
  const { data } = await client.post("/datasets/from-legacy-selection/", {
    name,
    trees,
  });
  return data;
}

export async function partitionLegacySelection({ name, trees, k }) {
  const { data } = await client.post("/datasets/partition-legacy-selection/", {
    name,
    trees,
    k,
  });
  return data;
}

export async function uploadDataset(file) {
  const name = file.name.replace(/\.[^.]+$/, "");
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  const { data } = await client.post("/datasets/", form);
  return data;
}

export async function updateDataset(id, { name, description }) {
  const { data } = await client.patch(`/datasets/${id}/`, { name, description });
  return data;
}

export async function deleteDataset(id) {
  await client.delete(`/datasets/${id}/`);
}

export async function deactivateDatasetTrees(datasetId, treeIds) {
  const { data } = await client.post(`/datasets/${datasetId}/trees/deactivate/`, {
    tree_ids: treeIds,
  });
  return data;
}
