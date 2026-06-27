import axios from "axios";
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
} from "./tokenStore.js";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

const client = axios.create({ baseURL });

client.interceptors.request.use((config) => {
  const access = getAccessToken();
  if (access) {
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || original._retried) {
      return Promise.reject(error);
    }

    const refresh = getRefreshToken();
    if (!refresh) {
      clearTokens();
      return Promise.reject(error);
    }

    original._retried = true;
    try {
      const { data } = await axios.post(`${baseURL}/auth/token/refresh/`, {
        refresh,
      });
      setTokens({ access: data.access });
      original.headers.Authorization = `Bearer ${data.access}`;
      return client(original);
    } catch (refreshError) {
      clearTokens();
      return Promise.reject(refreshError);
    }
  }
);

export default client;
