import { Link } from "react-router-dom";

import { useAuth } from "../../app/auth";
import StatusBadge from "../../components/common/StatusBadge";

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Dashboard</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">Benvenuto, {user?.name}</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <article className="rounded-2xl bg-slate-50 p-5">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Email</p>
            <p className="mt-2 text-sm font-medium">{user?.email}</p>
          </article>
          <article className="rounded-2xl bg-slate-50 p-5">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Ruolo</p>
            <p className="mt-2 text-sm font-medium">{user?.role}</p>
          </article>
          <article className="rounded-2xl bg-slate-50 p-5">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">OpenAI API Key</p>
            <div className="mt-2">
              <StatusBadge active={user?.openai_key_configured} />
            </div>
          </article>
        </div>
        <div className="mt-6">
          <Link className="text-sm font-semibold text-accent hover:underline" to="/profile">
            Apri User Detail
          </Link>
        </div>
      </section>
    </div>
  );
}
