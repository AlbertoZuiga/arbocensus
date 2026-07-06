import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Usuarios from "./Usuarios.jsx";
import { fetchUsers } from "@/api/users.js";

vi.mock("@/api/users.js", () => ({
  fetchUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deactivateUser: vi.fn(),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Usuarios />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchUsers.mockReset();
});

describe("Usuarios", () => {
  it("renders a row per user with name, email, role and state", async () => {
    fetchUsers.mockResolvedValue([
      {
        id: "u1",
        username: "alovelace",
        first_name: "Ada",
        last_name: "Lovelace",
        email: "ada@example.com",
        role: "admin",
        role_display: "Admin",
        is_active: true,
      },
    ]);
    renderPage();

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
  });

  it("shows inactive state and hides the deactivate action", async () => {
    fetchUsers.mockResolvedValue([
      {
        id: "u2",
        username: "ghopper",
        first_name: "",
        last_name: "",
        email: "grace@example.com",
        role: "surveyor",
        role_display: "Surveyor",
        is_active: false,
      },
    ]);
    renderPage();

    expect(await screen.findByText("ghopper")).toBeInTheDocument();
    expect(screen.getByText("Inactivo")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Desactivar" }),
    ).not.toBeInTheDocument();
  });

  it("opens the create dialog", async () => {
    fetchUsers.mockResolvedValue([]);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Nuevo usuario" }));
    expect(await screen.findByLabelText("Usuario")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
  });

  it("shows an empty message when there are no users", async () => {
    fetchUsers.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Aún no hay usuarios.")).toBeInTheDocument();
  });

  it("shows an error alert when the request fails", async () => {
    fetchUsers.mockRejectedValue(new Error("boom"));
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/No se pudieron cargar/)).toBeInTheDocument(),
    );
  });
});
