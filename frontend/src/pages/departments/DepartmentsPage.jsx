import { useEffect, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

export default function DepartmentsPage() {
  const { token } = useAuth();
  const [departments, setDepartments] = useState([]);

  useEffect(() => {
    apiRequest("/departments", {}, token)
      .then((data) => setDepartments(data.items))
      .catch(() => setDepartments([]));
  }, [token]);

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
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
    </section>
  );
}
