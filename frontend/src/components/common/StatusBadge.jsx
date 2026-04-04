export default function StatusBadge({ active, trueLabel = "Configurata", falseLabel = "Non configurata" }) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"
      }`}
    >
      {active ? trueLabel : falseLabel}
    </span>
  );
}
