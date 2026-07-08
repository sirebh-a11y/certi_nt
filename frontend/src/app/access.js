const FULL_ACCESS_DEPARTMENT = "it";
const QUALITY_AREA_DEPARTMENTS = ["it", "qualita"];

const PAGE_ACCESS = {
  dashboard: { departments: ["all"] },
  acquisitionUpload: { departments: ["it", "qualita", "laboratorio", "produzione"] },
  acquisition: { departments: ["it", "qualita", "laboratorio", "produzione"] },
  certification: { departments: ["it", "qualita", "laboratorio"] },
  certificateRegister: { departments: ["all"] },
  qualityEvaluation: { departments: ["it", "qualita", "direzione"] },
  supplierKpi: { departments: ["it", "qualita", "direzione"] },
  supplierCalendar: { departments: ["it", "qualita", "direzione"] },
  standards: { departments: ["it", "qualita", "laboratorio"] },
  customerRequirements: { departments: ["it", "qualita"] },
  notes: { departments: ["it", "qualita"] },
  supplierCodes: { departments: ["it", "qualita"] },
  suppliers: { departments: ["it", "qualita"] },
  clients: { departments: ["it", "qualita"] },
  users: { itAdminOnly: true },
  departments: { itAdminOnly: true },
  logs: { itAdminOnly: true },
  integrations: { itAdminOnly: true },
  ai: { itAdminOnly: true },
  emailSettings: { itAdminOnly: true },
};

export function normalizeDepartmentName(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function isItAdmin(user) {
  return user?.role === "admin" && normalizeDepartmentName(user?.department) === FULL_ACCESS_DEPARTMENT;
}

export function isQualityAreaUser(user) {
  return QUALITY_AREA_DEPARTMENTS.includes(normalizeDepartmentName(user?.department));
}

export function canEditQualitySetup(user) {
  return user?.role === "admin" && isQualityAreaUser(user);
}

export function canReopenQualityFlow(user) {
  return ["admin", "manager"].includes(user?.role) && isQualityAreaUser(user);
}

export function canGenerateFinalCertificatePdf(user) {
  return isQualityAreaUser(user);
}

export function canAccessPage(user, pageKey) {
  if (!user || !pageKey) {
    return false;
  }

  if (isItAdmin(user)) {
    return true;
  }

  const rule = PAGE_ACCESS[pageKey];
  if (!rule) {
    return false;
  }

  if (rule.itAdminOnly) {
    return false;
  }

  const department = normalizeDepartmentName(user.department);
  return rule.departments?.includes("all") || rule.departments?.includes(department);
}
