import { useEffect, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const permissionColumns = [
  "IT admin",
  "Qualita admin",
  "Qualita manager",
  "Qualita user",
  "Laboratorio",
  "Produzione",
  "Amministrazione",
  "Direzione",
];

const permissionRows = [
  {
    label: "Carica documenti",
    values: ["opera", "opera", "opera", "opera", "opera", "opera", "no", "no"],
  },
  {
    label: "Incoming materiale",
    values: ["opera", "opera", "opera", "opera", "opera", "opera", "no", "no"],
  },
  {
    label: "Conferma match / chimica / proprieta / note",
    values: ["opera", "opera", "opera", "opera", "opera", "no", "no", "no"],
  },
  {
    label: "Valutazione qualita",
    values: ["opera", "opera", "opera", "opera", "no", "no", "no", "consulta"],
  },
  {
    label: "Certificazione OL",
    values: ["opera", "opera", "opera", "opera", "consulta", "no", "no", "no"],
  },
  {
    label: "Crea / modifica Word certificato",
    values: ["opera", "opera", "opera", "opera", "no", "no", "no", "no"],
  },
  {
    label: "Genera PDF finale",
    values: ["opera", "opera", "opera", "opera", "no", "no", "no", "no"],
  },
  {
    label: "Riapri PDF chiuso",
    values: ["opera", "opera", "opera", "no", "no", "no", "no", "no"],
  },
  {
    label: "Registro certificazione",
    values: ["opera", "opera", "opera", "opera", "consulta", "no", "consulta", "consulta"],
  },
  {
    label: "Scarica Word / PDF",
    values: ["opera", "opera", "opera", "opera", "consulta", "no", "consulta", "consulta"],
  },
  {
    label: "Valutazione fornitori e KPI",
    values: ["opera", "opera", "opera", "opera", "no", "no", "no", "consulta"],
  },
  {
    label: "Standard / requisiti / note / codici fornitori",
    values: ["opera", "opera", "opera", "opera", "consulta", "no", "no", "no"],
  },
  {
    label: "Fornitori e clienti",
    values: ["opera", "opera", "opera", "opera", "no", "no", "no", "no"],
  },
  {
    label: "Utenti / reparti / log",
    values: ["opera", "no", "no", "no", "no", "no", "no", "no"],
  },
  {
    label: "Database / email / assistente AI",
    values: ["opera", "no", "no", "no", "no", "no", "no", "no"],
  },
];

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
    <span className={`inline-flex min-w-20 justify-center rounded-lg border px-2.5 py-1 text-xs font-semibold ${permissionClasses[value]}`}>
      {permissionLabels[value]}
    </span>
  );
}

export default function DepartmentsPage() {
  const { token } = useAuth();
  const [departments, setDepartments] = useState([]);

  useEffect(() => {
    apiRequest("/departments", {}, token)
      .then((data) => setDepartments(data.items))
      .catch(() => setDepartments([]));
  }, [token]);

  return (
    <section className="space-y-6 rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <div>
        <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Reparti</p>
        <h2 className="mt-2 text-2xl font-semibold">Departments</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {departments.map((department) => (
            <article className="rounded-2xl bg-slate-50 p-5" key={department.id}>
              <h3 className="text-lg font-semibold">{department.name}</h3>
              <p className="mt-2 text-sm text-slate-500">{department.description}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Permessi</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Matrice permessi</h3>
            <p className="mt-1 text-sm text-slate-500">Vista riepilogativa: non modifica utenti, reparti o permessi reali.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <PermissionBadge value="opera" />
            <PermissionBadge value="consulta" />
            <PermissionBadge value="no" />
          </div>
        </div>

        <div className="mt-5 overflow-x-auto rounded-2xl border border-border">
          <table className="min-w-[1180px] divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="sticky left-0 z-10 bg-slate-50 px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Attivita / pagina
                </th>
                {permissionColumns.map((column) => (
                  <th className="px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" key={column}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {permissionRows.map((row) => (
                <tr key={row.label}>
                  <td className="sticky left-0 z-10 bg-white px-4 py-3 font-semibold text-slate-900">{row.label}</td>
                  {row.values.map((value, index) => (
                    <td className="px-3 py-3 text-center" key={`${row.label}-${permissionColumns[index]}`}>
                      <PermissionBadge value={value} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
