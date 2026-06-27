import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore.js";

export default function LogoutButton() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <button
      type="button"
      onClick={handleLogout}
      className="rounded bg-slate-200 px-4 py-2 font-semibold text-slate-700"
    >
      Cerrar sesión
    </button>
  );
}
