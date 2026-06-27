import { Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore.js";
import { HOME_BY_ROLE } from "../constants/roles.js";

export default function ProtectedRoute({ requiredRole, children }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole && user && user.role !== requiredRole) {
    return <Navigate to={HOME_BY_ROLE[user.role] ?? "/login"} replace />;
  }

  return children;
}
