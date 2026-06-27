import { Route, Routes } from "react-router-dom";
import Login from "./pages/Login.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import LogoutButton from "./components/LogoutButton.jsx";
import AdminLayout from "./layouts/AdminLayout.jsx";
import AdminHome from "./pages/admin/AdminHome.jsx";
import Datasets from "./pages/admin/Datasets.jsx";
import Censadores from "./pages/admin/Censadores.jsx";
import { useSession } from "./hooks/useSession.js";
import { ROLES } from "./constants/roles.js";

function SurveyorHome() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50">
      <h1 className="text-3xl font-bold text-emerald-700">Arbocensus móvil</h1>
      <LogoutButton />
    </main>
  );
}

export default function App() {
  const { isBootstrapping } = useSession();

  if (isBootstrapping) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-slate-500">Cargando…</p>
      </main>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute requiredRole={ROLES.SURVEYOR}>
            <SurveyorHome />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute requiredRole={ROLES.ADMIN}>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminHome />} />
        <Route path="datasets" element={<Datasets />} />
        <Route path="censadores" element={<Censadores />} />
      </Route>
    </Routes>
  );
}
