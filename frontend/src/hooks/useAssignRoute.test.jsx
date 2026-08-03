import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../api/routes.js", () => ({
  assignRoute: vi.fn(),
}));

import { assignRoute } from "../api/routes.js";
import { useToastStore } from "../store/toastStore.js";
import { useAssignRoute } from "./useAssignRoute.js";

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function makeWrapper(client) {
  return function Wrapper({ children }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

describe("useAssignRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useToastStore.setState({ toasts: [] });
  });

  it("assigns a surveyor and invalidates routes and surveyors queries", async () => {
    assignRoute.mockResolvedValue({ id: "r1", surveyor: "u1" });
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useAssignRoute(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ routeId: "r1", surveyorId: "u1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(assignRoute).toHaveBeenCalledWith("r1", "u1");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["routes"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["surveyors"] });
  });

  it("passes surveyorId null through to unassign a route", async () => {
    assignRoute.mockResolvedValue({ id: "r1", surveyor: null });
    const client = makeClient();
    const { result } = renderHook(() => useAssignRoute(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ routeId: "r1", surveyorId: null });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(assignRoute).toHaveBeenCalledWith("r1", null);
  });

  it("shows an error toast when the assignment fails", async () => {
    assignRoute.mockRejectedValue({
      response: { data: { detail: "Ruta ya iniciada" } },
    });
    const client = makeClient();
    const { result } = renderHook(() => useAssignRoute(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ routeId: "r1", surveyorId: "u1" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0]).toMatchObject({
      variant: "error",
      message: "Ruta ya iniciada",
    });
  });

  it("falls back to a generic error toast without response detail", async () => {
    assignRoute.mockRejectedValue(new Error("network"));
    const client = makeClient();
    const { result } = renderHook(() => useAssignRoute(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ routeId: "r1", surveyorId: "u1" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(useToastStore.getState().toasts[0]).toMatchObject({
      variant: "error",
      message: "No se pudo asignar la ruta",
    });
  });
});
