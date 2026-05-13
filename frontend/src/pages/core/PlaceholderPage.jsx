export default function PlaceholderPage({ eyebrow, title, description }) {
  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <p className="text-sm uppercase tracking-[0.3em] text-slate-500">{eyebrow}</p>
      <h2 className="mt-2 text-2xl font-semibold text-slate-950">{title}</h2>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>
      <div className="mt-8 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-6 text-sm text-slate-500">
        Placeholder: questa pagina e' pronta per essere collegata alla logica applicativa quando definiremo campi, filtri e azioni.
      </div>
    </section>
  );
}
