import { Route, Routes } from "react-router-dom";
import Login from "./pages/Login.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import { ROLES } from "./constants/roles.js";

function AdminHome() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <h1 className="text-3xl font-bold text-emerald-700">Arbocensus</h1>
    </main>
  );
}

function SurveyorHome() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <h1 className="text-3xl font-bold text-emerald-700">Arbocensus móvil</h1>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute requiredRole={ROLES.ADMIN}>
            <AdminHome />
          </ProtectedRoute>
        }
      />
      <Route
        path="/m"
        element={
          <ProtectedRoute requiredRole={ROLES.SURVEYOR}>
            <SurveyorHome />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
