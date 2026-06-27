import { useLogout } from "../hooks/useLogout.js";

export default function LogoutButton() {
  const handleLogout = useLogout();

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
