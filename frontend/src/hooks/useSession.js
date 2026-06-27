import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import client from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";

export function useSession() {
  const navigate = useNavigate();
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);
  const logout = useAuthStore((state) => state.logout);

  const { data, error } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const response = await client.get("/auth/me/");
      return response.data;
    },
    enabled: !!accessToken,
    retry: false,
  });

  useEffect(() => {
    if (data) setUser(data);
  }, [data, setUser]);

  useEffect(() => {
    if (error?.response?.status === 401) {
      logout();
      navigate("/login", { replace: true });
    }
  }, [error, logout, navigate]);

  return { isBootstrapping: !!accessToken && !user && !error };
}
