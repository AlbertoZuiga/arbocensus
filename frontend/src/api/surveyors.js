import client from "./client.js";

export async function fetchSurveyors() {
  const surveyors = [];
  let page = 1;

  for (;;) {
    const { data } = await client.get("/auth/surveyors/", { params: { page } });
    if (Array.isArray(data)) return data;

    surveyors.push(...data.results);
    if (!data.next) break;
    page += 1;
  }

  return surveyors;
}
