import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../store/authStore.js";

export function useLogout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logout = useAuthStore((state) => state.logout);

  return useCallback(() => {
    logout();
    queryClient.removeQueries({ queryKey: ["me"] });
    navigate("/login", { replace: true });
  }, [logout, queryClient, navigate]);
}
