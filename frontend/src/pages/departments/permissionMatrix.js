import {
  canAccessPage,
  canEditQualitySetup,
  canGenerateFinalCertificatePdf,
  canReopenQualityFlow,
} from "../../app/access.js";

export const ROLE_OPTIONS = [
  { value: "admin", label: "Admin" },
  { value: "manager", label: "Manager" },
  { value: "user", label: "User" },
];

export const DEPARTMENT_ORDER = [
  "IT",
  "Qualità",
  "Incoming",
  "Laboratorio",
  "Produzione",
  "Amministrazione",
  "Direzione",
];

// Access shown by the normal app UI. The backend audit is documented separately:
// this display must never be treated as an authorization check.
export const PERMISSION_GROUPS = [
  {
    title: "Flusso certificazione",
    rows: [
      { id: "dashboard", label: "Dashboard", page: "dashboard", mode: "read" },
      { id: "ddt-list", label: "DDT da certificare · consultazione", page: "certification", mode: "read" },
      { id: "ddt-decide", label: "DDT da certificare · escludi / ripristina", page: "certification", mode: "action", canOperate: canEditQualitySetup },
      { id: "upload", label: "Carica documenti e inserimento manuale", page: "acquisitionUpload", mode: "action" },
      { id: "incoming-list", label: "Incoming materiale · consultazione", page: "acquisition", mode: "read" },
      { id: "incoming-checks", label: "Incoming · match, chimica, proprietà, note", page: "acquisition", mode: "action" },
      { id: "gemba", label: "Gemba Walk · stampa", page: "acquisition", mode: "action" },
      { id: "incoming-quality", label: "Incoming · valutazione finale", page: "acquisition", mode: "action" },
      { id: "incoming-reopen", label: "Incoming · riapri valutazione", page: "acquisition", mode: "action", canOperate: canReopenQualityFlow },
      { id: "incoming-delete", label: "Incoming · elimina riga", page: "acquisition", mode: "action", canOperate: canEditQualitySetup },
      { id: "certification-list", label: "Certificazione OL · consultazione", page: "certification", mode: "read" },
      { id: "certification-standard", label: "Certificazione · conferma standard", page: "certification", mode: "action" },
      { id: "certification-word", label: "Certificazione · crea / modifica Word", page: "certification", mode: "action" },
      { id: "register", label: "Registro certificazione · consultazione e download", page: "certificateRegister", mode: "read" },
      { id: "pdf-generate", label: "Registro · genera PDF finale", page: "certificateRegister", mode: "action", canOperate: canGenerateFinalCertificatePdf },
      { id: "pdf-reopen", label: "Registro · riapri PDF finale", page: "certificateRegister", mode: "action", canOperate: canReopenQualityFlow },
    ],
  },
  {
    title: "Valutazione fornitori",
    rows: [
      { id: "quality-evaluation", label: "Valutazione · consulta e aggiorna", page: "qualityEvaluation", mode: "action" },
      { id: "supplier-kpi", label: "KPI · consultazione", page: "supplierKpi", mode: "read" },
      { id: "supplier-kpi-export", label: "KPI · esportazione XLSX", page: "supplierKpi", mode: "action" },
      { id: "supplier-calendar", label: "Calendario · consulta e aggiorna", page: "supplierCalendar", mode: "action" },
    ],
  },
  {
    title: "Strumenti qualità e anagrafica",
    rows: [
      { id: "standards", label: "Standards · consulta e aggiorna", page: "standards", mode: "action" },
      { id: "customer-requirements", label: "Requisiti Cliente", page: "customerRequirements", mode: "editable", canOperate: canEditQualitySetup },
      { id: "notes", label: "Note standard", page: "notes", mode: "editable", canOperate: canEditQualitySetup },
      { id: "supplier-codes", label: "Codici fornitori", page: "supplierCodes", mode: "editable", canOperate: canEditQualitySetup },
      { id: "suppliers", label: "Fornitori", page: "suppliers", mode: "editable", canOperate: canEditQualitySetup },
      { id: "clients", label: "Clienti", page: "clients", mode: "read" },
    ],
  },
  {
    title: "Amministrazione tecnica",
    rows: [
      { id: "users", label: "Utenti · gestione", page: "users", mode: "action" },
      { id: "departments", label: "Reparti · consultazione", page: "departments", mode: "read" },
      { id: "logs", label: "Log · consultazione", page: "logs", mode: "read" },
      { id: "integrations", label: "Database e connettori · configurazione", page: "integrations", mode: "action" },
      { id: "ai", label: "Assistente AI · configurazione", page: "ai", mode: "action" },
      { id: "email", label: "Email · configurazione", page: "emailSettings", mode: "action" },
    ],
  },
];

export function sortDepartments(departments) {
  const order = new Map(DEPARTMENT_ORDER.map((name, index) => [name, index]));
  return [...departments].sort((left, right) =>
    (order.get(left.name) ?? DEPARTMENT_ORDER.length) - (order.get(right.name) ?? DEPARTMENT_ORDER.length)
    || left.name.localeCompare(right.name, "it"));
}

export function permissionLevel(row, user) {
  if (!canAccessPage(user, row.page)) return "no";
  if (row.mode === "read") return "consulta";
  if (row.canOperate && !row.canOperate(user)) {
    return row.mode === "editable" ? "consulta" : "no";
  }
  return "opera";
}
