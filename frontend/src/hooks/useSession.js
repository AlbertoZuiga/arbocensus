import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import client from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";
import { useLogout } from "./useLogout.js";

export function useSession() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);
  const logout = useLogout();

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
    if (error) logout();
  }, [error, logout]);

  return { isBootstrapping: !!accessToken && !user && !error };
}
