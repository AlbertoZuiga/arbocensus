import client from "./client.js";

export async function fetchUsers() {
  const users = [];
  let page = 1;

  for (;;) {
    const { data } = await client.get("/auth/users/", { params: { page } });
    if (Array.isArray(data)) return data;

    users.push(...data.results);
    if (!data.next) break;
    page += 1;
  }

  return users;
}

export async function createUser(payload) {
  const { data } = await client.post("/auth/users/", payload);
  return data;
}

export async function updateUser(id, payload) {
  const { data } = await client.patch(`/auth/users/${id}/`, payload);
  return data;
}

export async function deactivateUser(id) {
  await client.delete(`/auth/users/${id}/`);
}
