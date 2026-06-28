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

export async function uploadDataset(file) {
  const name = file.name.replace(/\.[^.]+$/, "");
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  const { data } = await client.post("/datasets/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
