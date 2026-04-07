import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { EMAIL_ERROR_MESSAGE, isValidEmail } from "../../app/validation";

const initialForm = {
  ragione_sociale: "",
  partita_iva: "",
  codice_fiscale: "",
  indirizzo: "",
  cap: "",
  citta: "",
  provincia: "",
  nazione: "",
  email: "",
  telefono: "",
  attivo: true,
  note: "",
};

export default function NewSupplierPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (form.email && !isValidEmail(form.email)) {
      setError(EMAIL_ERROR_MESSAGE);
      return;
    }

    setSubmitting(true);
    try {
      const supplier = await apiRequest(
        "/suppliers",
        {
          method: "POST",
          body: JSON.stringify({
            ...form,
            email: form.email || null,
          }),
        },
        token,
      );
      navigate(`/suppliers/${supplier.id}`, { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Fornitori</p>
      <h2 className="mt-2 text-2xl font-semibold">Nuovo Fornitore</h2>
      <form className="mt-8 grid gap-4 md:grid-cols-2" noValidate onSubmit={handleSubmit}>
        <div className="md:col-span-2">
          <label className="mb-2 block text-sm font-medium">Ragione sociale</label>
          <input
            required
            value={form.ragione_sociale}
            onChange={(event) => setForm({ ...form, ragione_sociale: event.target.value })}
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Partita IVA</label>
          <input value={form.partita_iva} onChange={(event) => setForm({ ...form, partita_iva: event.target.value })} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Codice fiscale</label>
          <input
            value={form.codice_fiscale}
            onChange={(event) => setForm({ ...form, codice_fiscale: event.target.value })}
          />
        </div>
        <div className="md:col-span-2">
          <label className="mb-2 block text-sm font-medium">Indirizzo</label>
          <input value={form.indirizzo} onChange={(event) => setForm({ ...form, indirizzo: event.target.value })} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">CAP</label>
          <input value={form.cap} onChange={(event) => setForm({ ...form, cap: event.target.value })} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Città</label>
          <input value={form.citta} onChange={(event) => setForm({ ...form, citta: event.target.value })} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Provincia</label>
          <input value={form.provincia} onChange={(event) => setForm({ ...form, provincia: event.target.value })} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Nazione</label>
          <input value={form.nazione} onChange={(event) => setForm({ ...form, nazione: event.target.value })} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Email</label>
          <input
            inputMode="email"
            type="text"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Telefono</label>
          <input value={form.telefono} onChange={(event) => setForm({ ...form, telefono: event.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label className="mb-2 block text-sm font-medium">Stato</label>
          <select
            value={form.attivo ? "active" : "inactive"}
            onChange={(event) => setForm({ ...form, attivo: event.target.value === "active" })}
          >
            <option value="active">Attivo</option>
            <option value="inactive">Disattivo</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="mb-2 block text-sm font-medium">Note</label>
          <textarea rows={5} value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} />
        </div>
        {error ? <p className="md:col-span-2 text-sm text-rose-600">{error}</p> : null}
        <div className="md:col-span-2">
          <button
            className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Creazione..." : "Crea fornitore"}
          </button>
        </div>
      </form>
    </section>
  );
}
