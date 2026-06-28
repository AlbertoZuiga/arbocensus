import { create } from "zustand";

let nextId = 0;

export const useToastStore = create((set) => ({
  toasts: [],
  push: (toast) => {
    const id = nextId++;
    set((state) => ({ toasts: [...state.toasts, { id, ...toast }] }));
    return id;
  },
  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

export const toast = {
  success: (message) =>
    useToastStore.getState().push({ variant: "success", message }),
  error: (message) =>
    useToastStore.getState().push({ variant: "error", message }),
};
