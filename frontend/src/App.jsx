import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import AdminLayout from "./layouts/AdminLayout.jsx";
import AdminHome from "./pages/admin/AdminHome.jsx";
import Datasets from "./pages/admin/Datasets.jsx";
import DatasetDetail from "./pages/admin/DatasetDetail.jsx";
import LegacyImport from "./pages/admin/LegacyImport.jsx";
import JobDetail from "./pages/admin/JobDetail.jsx";
import Usuarios from "./pages/admin/Usuarios.jsx";
import { useSession } from "./hooks/useSession.js";
import { useAuthStore } from "./store/authStore.js";
import { HOME_BY_ROLE, ROLES } from "./constants/roles.js";
import SurveyorRoutePage from "./pages/surveyor/SurveyorRoutePage.jsx";

function NotFoundRedirect() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const target = accessToken ? HOME_BY_ROLE[user?.role] ?? "/login" : "/login";
  return <Navigate to={target} replace />;
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
            <SurveyorRoutePage />
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
        <Route path="datasets/legacy-import" element={<LegacyImport />} />
        <Route path="datasets/:id" element={<DatasetDetail />} />
        <Route path="datasets/:id/jobs/:jobId" element={<JobDetail />} />
        <Route path="usuarios" element={<Usuarios />} />
      </Route>
      <Route path="*" element={<NotFoundRedirect />} />
    </Routes>
  );
}
