import { useNavigate } from "react-router-dom";

import { useAuth } from "../../app/auth";

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="border-b border-border bg-panel px-6 py-4">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">CERTI_nt</p>
          <h1 className="text-xl font-semibold text-ink">Core Platform</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-sm font-semibold">{user?.name}</p>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{user?.role}</p>
          </div>
          <button
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-ink transition hover:border-accent hover:text-accent"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
