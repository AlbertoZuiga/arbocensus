import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
}));

import { createJob } from "@/api/optimization";
import RoutingConfigForm from "./RoutingConfigForm.jsx";

function renderForm(props = {}) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <RoutingConfigForm datasetId="d1" {...props} />
    </QueryClientProvider>
  );
}

describe("RoutingConfigForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders editable defaults (2h / 3h / 300s)", () => {
    renderForm();
    expect(screen.getByLabelText(/Tiempo mínimo por ruta/)).toHaveValue(2);
    expect(screen.getByLabelText(/Tiempo máximo por ruta/)).toHaveValue(3);
    expect(screen.getByLabelText(/Tiempo de servicio/)).toHaveValue(300);
  });

  it("submits with hours converted to seconds", async () => {
    createJob.mockResolvedValue({ id: "j1", status: "queued" });
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    await waitFor(() =>
      expect(createJob).toHaveBeenCalledWith({
        dataset: "d1",
        minRouteTimeSec: 7200,
        maxRouteTimeSec: 10800,
        serviceTimeSec: 300,
      })
    );
  });

  it("converts edited hour values to seconds", async () => {
    createJob.mockResolvedValue({ id: "j1" });
    const user = userEvent.setup();
    renderForm();

    const minInput = screen.getByLabelText(/Tiempo mínimo por ruta/);
    await user.clear(minInput);
    await user.type(minInput, "1.5");
    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    await waitFor(() =>
      expect(createJob).toHaveBeenCalledWith(
        expect.objectContaining({ minRouteTimeSec: 5400 })
      )
    );
  });

  it("calls onJobCreated with the created job", async () => {
    const job = { id: "j1", status: "queued" };
    createJob.mockResolvedValue(job);
    const onJobCreated = vi.fn();
    const user = userEvent.setup();
    renderForm({ onJobCreated });

    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    await waitFor(() => expect(onJobCreated).toHaveBeenCalledWith(job));
  });
});
