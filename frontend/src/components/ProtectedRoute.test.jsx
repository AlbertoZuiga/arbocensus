import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./ProtectedRoute.jsx";
import { useAuthStore } from "../store/authStore.js";
import { ROLES } from "../constants/roles.js";

function renderAdminAt() {
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Routes>
        <Route path="/login" element={<div>login page</div>} />
        <Route path="/" element={<div>surveyor home</div>} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute requiredRole={ROLES.ADMIN}>
              <div>admin content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, user: null });
});

describe("ProtectedRoute", () => {
  it("redirects to /login when there is no access token", () => {
    renderAdminAt();
    expect(screen.getByText("login page")).toBeInTheDocument();
    expect(screen.queryByText("admin content")).not.toBeInTheDocument();
  });

  it("redirects a surveyor away from an admin route to their home", () => {
    useAuthStore.setState({
      accessToken: "token",
      user: { username: "bob", role: ROLES.SURVEYOR },
    });
    renderAdminAt();
    expect(screen.getByText("surveyor home")).toBeInTheDocument();
    expect(screen.queryByText("admin content")).not.toBeInTheDocument();
  });

  it("renders the protected content for a matching role", () => {
    useAuthStore.setState({
      accessToken: "token",
      user: { username: "alice", role: ROLES.ADMIN },
    });
    renderAdminAt();
    expect(screen.getByText("admin content")).toBeInTheDocument();
  });
});
