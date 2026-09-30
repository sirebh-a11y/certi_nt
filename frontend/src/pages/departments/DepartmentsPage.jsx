import { Fragment, useEffect, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { PERMISSION_GROUPS, ROLE_OPTIONS, permissionLevel, sortDepartments } from "./permissionMatrix";

const permissionLabels = {
  opera: "Opera",
  consulta: "Consulta",
  no: "No",
};

const permissionClasses = {
  opera: "border-emerald-200 bg-emerald-50 text-emerald-800",
  consulta: "border-sky-200 bg-sky-50 text-sky-800",
  no: "border-slate-200 bg-slate-50 text-slate-500",
};

function PermissionBadge({ value }) {
  return (
    <span className={`inline-flex min-w-[58px] justify-center rounded-lg border px-1 py-1 text-[11px] font-semibold ${permissionClasses[value]}`}>
      {permissionLabels[value]}
    </span>
  );
}

export default function DepartmentsPage() {
  const { token } = useAuth();
  const [departments, setDepartments] = useState([]);
  const [selectedRole, setSelectedRole] = useState("admin");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiRequest("/departments", {}, token)
      .then((data) => {
        if (!cancelled) setDepartments(sortDepartments(data.items));
      })
      .catch(() => {
        if (!cancelled) setError("Non riesco a caricare i reparti. La matrice non è disponibile.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [token]);

  return (
    <section className="min-w-0 space-y-6 rounded-3xl border border-border bg-panel p-4 shadow-lg shadow-slate-200/40 sm:p-6">
      <div>
        <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Reparti</p>
        <h2 className="mt-2 text-2xl font-semibold">Reparti e accessi</h2>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {departments.map((department) => (
            <article className="rounded-2xl bg-slate-50 p-4" key={department.id}>
              <h3 className="text-base font-semibold">{department.name}</h3>
              <p className="mt-1 text-sm text-slate-500">{department.description}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="min-w-0 rounded-2xl border border-border bg-white p-3 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Permessi</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Matrice accessi dall’interfaccia</h3>
            <p className="mt-1 text-sm text-slate-500">Scegli il ruolo e confronta tutti i reparti. Questa vista non modifica i permessi.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <PermissionBadge value="opera" />
            <PermissionBadge value="consulta" />
            <PermissionBadge value="no" />
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <span className="text-sm font-semibold text-slate-700">Ruolo utente</span>
          <div aria-label="Ruolo da confrontare" className="inline-flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1" role="group">
            {ROLE_OPTIONS.map((role) => (
              <button
                aria-pressed={selectedRole === role.value}
                className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition ${selectedRole === role.value ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-white"}`}
                key={role.value}
                onClick={() => setSelectedRole(role.value)}
                type="button"
              >
                {role.label}
              </button>
            ))}
          </div>
          <span className="text-xs text-slate-500">Opera = può eseguire l’azione se i dati lo consentono; Consulta = lettura o download; No = funzione non disponibile nella pagina.</span>
        </div>

        {loading ? <p className="mt-4 text-sm text-slate-500">Caricamento reparti...</p> : null}
        {error ? <p className="mt-4 text-sm font-semibold text-rose-700" role="alert">{error}</p> : null}
        {!loading && !error ? <p className="mt-3 text-xs text-slate-500 md:hidden">Su uno schermo stretto, scorri la tabella verso destra per vedere gli altri reparti.</p> : null}
        {!loading && !error && departments.length > 0 ? <div className="mt-5 min-w-0 overflow-x-auto rounded-2xl border border-border">
          <table className="w-full min-w-[780px] table-fixed divide-y divide-slate-200 text-sm">
            <colgroup>
              <col className="w-[235px]" />
              {departments.map((department) => <col key={department.id} />)}
            </colgroup>
            <thead className="bg-slate-50">
              <tr>
                <th className="sticky left-0 z-10 bg-slate-50 px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500" scope="col">
                  Attività / pagina
                </th>
                {departments.map((department) => (
                  <th className="break-words px-1 py-3 text-center text-[11px] font-semibold leading-4 text-slate-600" key={department.id} scope="col">
                    {department.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {PERMISSION_GROUPS.map((group) => (
                <Fragment key={group.title}>
                  <tr className="bg-slate-100">
                    <th className="bg-slate-100 px-3 py-2 text-left text-xs font-bold text-slate-700" colSpan={departments.length + 1} scope="colgroup">{group.title}</th>
                  </tr>
                  {group.rows.map((row) => (
                    <tr key={row.id}>
                      <th className="sticky left-0 z-10 bg-white px-3 py-2.5 text-left text-xs font-semibold leading-4 text-slate-900" scope="row">{row.label}</th>
                      {departments.map((department) => (
                        <td className="px-1 py-2 text-center" key={`${row.id}-${department.id}`}>
                          <PermissionBadge value={permissionLevel(row, { department: department.name, role: selectedRole })} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div> : null}
      </div>
    </section>
  );
}
