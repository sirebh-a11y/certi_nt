import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { EMAIL_ERROR_MESSAGE, isValidEmail } from "../../app/validation";

const initialForm = {
  name: "",
  email: "",
  department: "administration",
  role: "user",
};

export default function NewUserPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [departments, setDepartments] = useState([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiRequest("/departments", {}, token)
      .then((data) => setDepartments(data.items))
      .catch((requestError) => setError(requestError.message));
  }, [token]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    if (!isValidEmail(form.email)) {
      setError(EMAIL_ERROR_MESSAGE);
      return;
    }

    setSubmitting(true);
    try {
      const user = await apiRequest(
        "/users",
        {
          method: "POST",
          body: JSON.stringify(form),
        },
        token,
      );
      navigate(`/users/${user.id}`, { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Utenti</p>
      <h2 className="mt-2 text-2xl font-semibold">New User</h2>
      <form className="mt-8 grid gap-4 md:grid-cols-2" noValidate onSubmit={handleSubmit}>
        <div className="md:col-span-2">
          <label className="mb-2 block text-sm font-medium">Nome</label>
          <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
        </div>
        <div className="md:col-span-2">
          <label className="mb-2 block text-sm font-medium">Email</label>
          <input
            type="text"
            inputMode="email"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            required
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Reparto</label>
          <select value={form.department} onChange={(event) => setForm({ ...form, department: event.target.value })}>
            {departments.map((department) => (
              <option key={department.id} value={department.name}>
                {department.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Ruolo</label>
          <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
            <option value="user">user</option>
            <option value="manager">manager</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <div className="md:col-span-2 text-sm text-slate-500">
          La password non viene impostata in creazione utente. Il primo accesso userà il flusso Set Password.
        </div>
        {error ? <p className="md:col-span-2 text-sm text-rose-600">{error}</p> : null}
        <div className="md:col-span-2">
          <button
            className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Creazione..." : "Crea utente"}
          </button>
        </div>
      </form>
    </section>
  );
}
