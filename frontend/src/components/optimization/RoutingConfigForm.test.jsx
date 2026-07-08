import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
  fetchFleetEstimate: vi.fn(),
}));

import { createJob, fetchFleetEstimate } from "@/api/optimization";
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
    fetchFleetEstimate.mockResolvedValue(null);
  });

  it("renders editable defaults (2h / 3h / 5min)", () => {
    renderForm();
    expect(screen.getByLabelText(/Tiempo mínimo por ruta/)).toHaveValue(2);
    expect(screen.getByLabelText(/Tiempo máximo por ruta/)).toHaveValue(3);
    expect(screen.getByLabelText(/Tiempo de censo por árbol/)).toHaveValue(5);
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
        strategy: "global",
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

  it("sends the default global strategy", async () => {
    createJob.mockResolvedValue({ id: "j1" });
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    await waitFor(() =>
      expect(createJob).toHaveBeenCalledWith(
        expect.objectContaining({ strategy: "global" })
      )
    );
  });

  it("disables submit while an active job exists for the dataset", async () => {
    renderForm({ hasActiveJob: true });

    expect(
      screen.getByRole("button", { name: "Generar rutas" })
    ).toBeDisabled();
    expect(
      screen.getByText("Ya hay una optimización en curso para este dataset.")
    ).toBeInTheDocument();
  });

  it("shows the fleet estimate hint when n_estimated is a number", async () => {
    fetchFleetEstimate.mockResolvedValue(4);
    renderForm();

    expect(await screen.findByText("Hasta 4 rutas aprox.")).toBeInTheDocument();
  });

  it("renders no hint when n_estimated is null", async () => {
    fetchFleetEstimate.mockResolvedValue(null);
    renderForm();

    await waitFor(() =>
      expect(fetchFleetEstimate).toHaveBeenCalledWith("d1", 7200, 300)
    );
    expect(screen.queryByText(/rutas aprox\./)).not.toBeInTheDocument();
  });

  it("refetches the estimate when min route time or service time change", async () => {
    fetchFleetEstimate.mockResolvedValue(4);
    const user = userEvent.setup();
    renderForm();

    await waitFor(() =>
      expect(fetchFleetEstimate).toHaveBeenCalledWith("d1", 7200, 300)
    );

    const serviceInput = screen.getByLabelText(/Tiempo de censo por árbol/);
    await user.clear(serviceInput);
    await user.type(serviceInput, "10");

    await waitFor(() =>
      expect(fetchFleetEstimate).toHaveBeenCalledWith("d1", 7200, 600)
    );
  });

  it("blocks submit and warns when min exceeds max", async () => {
    const user = userEvent.setup();
    renderForm();

    const maxInput = screen.getByLabelText(/Tiempo máximo por ruta/);
    await user.clear(maxInput);
    await user.type(maxInput, "1");

    expect(
      screen.getByText("El tiempo mínimo no puede ser mayor que el máximo.")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Generar rutas" })
    ).toBeDisabled();
    expect(createJob).not.toHaveBeenCalled();
  });
});
