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
  const emptyEstimate = {
    n_estimated: null,
    blocking: [],
    warnings: [],
    diagnostics: {},
  };

  beforeEach(() => {
    vi.clearAllMocks();
    fetchFleetEstimate.mockResolvedValue(emptyEstimate);
  });

  it("renders editable defaults (120min / 180min / 2min)", () => {
    renderForm();
    expect(screen.getByLabelText(/Tiempo mínimo por ruta/)).toHaveValue(120);
    expect(screen.getByLabelText(/Tiempo máximo por ruta/)).toHaveValue(180);
    expect(screen.getByLabelText(/Tiempo de censo por árbol/)).toHaveValue(2);
  });

  it("submits with minutes converted to seconds", async () => {
    createJob.mockResolvedValue([{ id: "j1", status: "queued" }]);
    const user = userEvent.setup();
    renderForm();

    await user.click(
      screen.getByRole("button", { name: "Generar y comparar rutas" })
    );

    await waitFor(() =>
      expect(createJob).toHaveBeenCalledWith({
        dataset: "d1",
        minRouteTimeSec: 7200,
        maxRouteTimeSec: 10800,
        serviceTimeSec: 120,
      })
    );
  });

  it("converts edited minute values to seconds", async () => {
    createJob.mockResolvedValue([{ id: "j1" }]);
    const user = userEvent.setup();
    renderForm();

    const minInput = screen.getByLabelText(/Tiempo mínimo por ruta/);
    await user.clear(minInput);
    await user.type(minInput, "90");
    await user.click(
      screen.getByRole("button", { name: "Generar y comparar rutas" })
    );

    await waitFor(() =>
      expect(createJob).toHaveBeenCalledWith(
        expect.objectContaining({ minRouteTimeSec: 5400 })
      )
    );
  });

  it("calls onJobCreated with the created jobs", async () => {
    const jobs = [{ id: "j1", status: "queued" }];
    createJob.mockResolvedValue(jobs);
    const onJobCreated = vi.fn();
    const user = userEvent.setup();
    renderForm({ onJobCreated });

    await user.click(
      screen.getByRole("button", { name: "Generar y comparar rutas" })
    );

    await waitFor(() => expect(onJobCreated).toHaveBeenCalledWith(jobs));
  });

  it("disables submit while an active job exists for the dataset", async () => {
    renderForm({ hasActiveJob: true });

    expect(
      screen.getByRole("button", { name: "Generar y comparar rutas" })
    ).toBeDisabled();
    expect(
      screen.getByText("Ya hay una optimización en curso para este dataset.")
    ).toBeInTheDocument();
  });

  it("shows the fleet estimate hint when n_estimated is a number", async () => {
    fetchFleetEstimate.mockResolvedValue({
      n_estimated: 4,
      blocking: [],
      warnings: [],
      diagnostics: {},
    });
    renderForm();

    expect(await screen.findByText("Hasta 4 rutas aprox.")).toBeInTheDocument();
  });

  it("renders no hint when n_estimated is null", async () => {
    renderForm();

    await waitFor(() =>
      expect(fetchFleetEstimate).toHaveBeenCalledWith("d1", 7200, 10800, 120)
    );
    expect(screen.queryByText(/rutas aprox\./)).not.toBeInTheDocument();
  });

  it("refetches the estimate when min route time or service time change", async () => {
    fetchFleetEstimate.mockResolvedValue({
      n_estimated: 4,
      blocking: [],
      warnings: [],
      diagnostics: {},
    });
    const user = userEvent.setup();
    renderForm();

    await waitFor(() =>
      expect(fetchFleetEstimate).toHaveBeenCalledWith("d1", 7200, 10800, 120)
    );

    const serviceInput = screen.getByLabelText(/Tiempo de censo por árbol/);
    await user.clear(serviceInput);
    await user.type(serviceInput, "10");

    await waitFor(() =>
      expect(fetchFleetEstimate).toHaveBeenCalledWith("d1", 7200, 10800, 600)
    );
  });

  it("shows blocking error and disables submit when blocking errors present", async () => {
    fetchFleetEstimate.mockResolvedValue({
      n_estimated: null,
      blocking: [
        {
          code: "service_exceeds_tmax",
          detail: "Ni un solo árbol alcanza a censarse dentro de una ruta.",
        },
      ],
      warnings: [],
      diagnostics: {},
    });
    renderForm();

    expect(
      await screen.findByText(
        "Ni un solo árbol alcanza a censarse dentro de una ruta."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Generar y comparar rutas" })
    ).toBeDisabled();
  });

  it("shows warning without blocking submit", async () => {
    fetchFleetEstimate.mockResolvedValue({
      n_estimated: 3,
      blocking: [],
      warnings: [
        { code: "padding_regime", detail: "Las rutas van a incluir relleno." },
      ],
      diagnostics: {},
    });
    renderForm();

    expect(
      await screen.findByText("Las rutas van a incluir relleno.")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Generar y comparar rutas" })
    ).not.toBeDisabled();
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
      screen.getByRole("button", { name: "Generar y comparar rutas" })
    ).toBeDisabled();
    expect(createJob).not.toHaveBeenCalled();
  });
});
