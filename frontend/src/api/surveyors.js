import client from "./client.js";

export async function fetchSurveyors() {
  const { data } = await client.get("/auth/surveyors/");
  return data.results ?? data;
}
