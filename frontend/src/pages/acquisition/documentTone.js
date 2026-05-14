const DOCUMENT_TONES = {
  certificato: {
    panel: "border-sky-200 bg-sky-50/85",
    viewport: "border-sky-200 bg-white/75",
    dashedViewport: "border-sky-300 bg-white/65",
    button: "border-sky-200 bg-white text-slate-700 hover:bg-sky-50",
  },
  ddt: {
    panel: "border-orange-300 bg-orange-100/90 shadow-sm shadow-orange-200/50",
    viewport: "border-orange-300 bg-orange-50/70",
    dashedViewport: "border-orange-400 bg-orange-50/70",
    button: "border-orange-300 bg-white text-slate-800 hover:bg-orange-50",
  },
};

export function documentTone(kind) {
  return DOCUMENT_TONES[kind] || DOCUMENT_TONES.certificato;
}
