import { useNavigate, useParams } from "react-router-dom";

const SECTION_TITLES = {
  "document-matching": "Matching documentale",
  chemistry: "Chimica",
  properties: "Proprietà",
  notes: "Note",
};

export default function AcquisitionSectionPlaceholderPage() {
  const navigate = useNavigate();
  const { sectionKey } = useParams();
  const title = SECTION_TITLES[sectionKey] || "Sezione";

  return (
    <section className="space-y-4">
      <div>
        <button className="text-sm font-medium text-accent hover:underline" onClick={() => navigate("/acquisition")} type="button">
          Torna alla lista
        </button>
        <p className="mt-3 text-sm uppercase tracking-[0.3em] text-slate-500">Incoming Quality</p>
        <h1 className="mt-1 text-3xl font-semibold text-slate-900">{title}</h1>
      </div>
    </section>
  );
}
