import { create } from "zustand";
import {
  getAccessToken,
  getRefreshToken,
  setTokens as persistTokens,
  clearTokens,
} from "../api/tokenStore.js";

export const useAuthStore = create((set) => ({
  accessToken: getAccessToken(),
  refreshToken: getRefreshToken(),
  user: null,
  setTokens: ({ access, refresh }) => {
    persistTokens({ access, refresh });
    set((state) => ({
      accessToken: access ?? state.accessToken,
      refreshToken: refresh ?? state.refreshToken,
    }));
  },
  setUser: (user) => set({ user }),
  logout: () => {
    clearTokens();
    set({ accessToken: null, refreshToken: null, user: null });
  },
}));
