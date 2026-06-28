export function getErrorMessage(error, fallback) {
  const data = error?.response?.data;
  if (data?.detail) return data.detail;
  if (data && typeof data === "object") {
    const first = Object.values(data)[0];
    if (Array.isArray(first) && first.length) return first[0];
    if (typeof first === "string") return first;
  }
  return fallback;
}
