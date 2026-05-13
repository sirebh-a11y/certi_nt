import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../../app/auth";

const navItems = [
  { label: "Dashboard", to: "/dashboard", roles: ["user", "manager", "admin"], icon: "dashboard" },
  { type: "section", label: "Flusso certificazione", key: "certification-flow" },
  { label: "Carica Documenti", to: "/acquisition/upload", roles: ["user", "manager", "admin"], icon: "upload" },
  { label: "Incoming materiale", to: "/acquisition", roles: ["user", "manager", "admin"], icon: "inbox" },
  { label: "Certificazione", to: "/quarta-taglio", roles: ["user", "manager", "admin"], icon: "certificate" },
  { label: "Registro certificazione", to: "/quarta-taglio/certificati", roles: ["user", "manager", "admin"], icon: "archive" },
  { type: "section", label: "Valutazione fornitori", key: "supplier-evaluation" },
  { label: "Valutazione", to: "/quality-evaluation", roles: ["user", "manager", "admin"], icon: "check" },
  { label: "KPI", to: "/supplier-kpi", roles: ["user", "manager", "admin"], icon: "chart" },
  { type: "section", label: "Strumenti qualità", key: "quality-tools" },
  { label: "Standards", to: "/standards", roles: ["user", "manager", "admin"], icon: "standards" },
  { label: "Note", to: "/notes", roles: ["user", "manager", "admin"], icon: "note" },
  { type: "section", label: "Anagrafica", key: "master-data" },
  { label: "Fornitori", to: "/suppliers", roles: ["user", "manager", "admin"], icon: "factory" },
  { label: "Clienti", to: "/clients", roles: ["user", "manager", "admin"], icon: "clients" },
  { type: "section", label: "Risorse", key: "resources" },
  { label: "Utenti", to: "/users", roles: ["manager", "admin"], icon: "users" },
  { label: "Reparti", to: "/departments", roles: ["admin"], icon: "departments" },
  { label: "Log", to: "/logs", roles: ["manager", "admin"], icon: "log" },
  { type: "section", label: "Connettori", key: "connectors" },
  { label: "Database", to: "/integrations", roles: ["admin"], icon: "database" },
  { label: "Assistente AI", to: "/ai", roles: ["admin"], icon: "ai" },
];

function SidebarIcon({ name }) {
  const commonProps = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    strokeWidth: 1.8,
    viewBox: "0 0 24 24",
  };

  const paths = {
    dashboard: (
      <>
        <rect x="4" y="4" width="6" height="6" rx="1.5" />
        <rect x="14" y="4" width="6" height="6" rx="1.5" />
        <rect x="4" y="14" width="6" height="6" rx="1.5" />
        <rect x="14" y="14" width="6" height="6" rx="1.5" />
      </>
    ),
    upload: (
      <>
        <path d="M12 15V4" />
        <path d="m8 8 4-4 4 4" />
        <path d="M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" />
      </>
    ),
    inbox: (
      <>
        <path d="M5 5h14l2 8v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5l2-8Z" />
        <path d="M3 13h5l2 3h4l2-3h5" />
      </>
    ),
    certificate: (
      <>
        <path d="M7 3h7l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
        <path d="M14 3v5h5" />
        <path d="m9 14 2 2 4-4" />
      </>
    ),
    archive: (
      <>
        <rect x="4" y="5" width="16" height="4" rx="1" />
        <path d="M6 9v9a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V9" />
        <path d="M10 13h4" />
      </>
    ),
    check: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="m8.5 12.5 2.2 2.2 4.8-5" />
      </>
    ),
    chart: (
      <>
        <path d="M5 19V5" />
        <path d="M5 19h14" />
        <path d="M8 15v-3" />
        <path d="M12 15V8" />
        <path d="M16 15v-5" />
      </>
    ),
    standards: (
      <>
        <path d="M5 4h14v16H5z" />
        <path d="M8 8h8" />
        <path d="M8 12h8" />
        <path d="M8 16h5" />
      </>
    ),
    note: (
      <>
        <path d="M6 4h12v16H6z" />
        <path d="M9 8h6" />
        <path d="M9 12h6" />
        <path d="M9 16h3" />
      </>
    ),
    factory: (
      <>
        <path d="M4 20V9l5 3V9l5 3V7h6v13H4Z" />
        <path d="M8 16h1" />
        <path d="M12 16h1" />
        <path d="M16 16h1" />
      </>
    ),
    clients: (
      <>
        <circle cx="9" cy="8" r="3" />
        <circle cx="17" cy="10" r="2.5" />
        <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
        <path d="M14.5 17.5A4.5 4.5 0 0 1 21 20" />
      </>
    ),
    users: (
      <>
        <circle cx="9" cy="8" r="3" />
        <circle cx="17" cy="10" r="2.5" />
        <path d="M4 20a5 5 0 0 1 10 0" />
        <path d="M15 17a4 4 0 0 1 5 3" />
      </>
    ),
    departments: (
      <>
        <rect x="9" y="3" width="6" height="5" rx="1" />
        <rect x="4" y="16" width="6" height="5" rx="1" />
        <rect x="14" y="16" width="6" height="5" rx="1" />
        <path d="M12 8v4" />
        <path d="M7 16v-4h10v4" />
      </>
    ),
    log: (
      <>
        <path d="M6 4h12v16H6z" />
        <path d="M9 8h6" />
        <path d="M9 12h6" />
        <path d="M9 16h4" />
      </>
    ),
    database: (
      <>
        <ellipse cx="12" cy="6" rx="7" ry="3" />
        <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
        <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      </>
    ),
    ai: (
      <>
        <path d="M12 3v4" />
        <path d="M12 17v4" />
        <path d="M3 12h4" />
        <path d="M17 12h4" />
        <path d="m6.3 6.3 2.8 2.8" />
        <path d="m14.9 14.9 2.8 2.8" />
        <path d="m17.7 6.3-2.8 2.8" />
        <path d="m9.1 14.9-2.8 2.8" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
  };

  return (
    <svg aria-hidden="true" className="h-4 w-4" {...commonProps}>
      {paths[name] ?? paths.dashboard}
    </svg>
  );
}

export default function Sidebar() {
  const { user } = useAuth();
  const location = useLocation();
  const visibleNavItems = [];

  navItems.forEach((item, index) => {
    if (item.type !== "section") {
      if (item.roles.includes(user?.role)) {
        visibleNavItems.push(item);
      }
      return;
    }

    const nextSectionIndex = navItems.findIndex((nextItem, nextIndex) => nextIndex > index && nextItem.type === "section");
    const sectionItems = navItems.slice(index + 1, nextSectionIndex === -1 ? navItems.length : nextSectionIndex);
    const hasVisibleItem = sectionItems.some((nextItem) => nextItem.roles.includes(user?.role));

    if (hasVisibleItem) {
      visibleNavItems.push(item);
    }
  });

  function isNavItemActive(item, isActive) {
    if (item.to === "/acquisition") {
      return location.pathname === "/acquisition" || /^\/acquisition\/\d+/.test(location.pathname);
    }
    if (item.to === "/quarta-taglio") {
      return location.pathname === "/quarta-taglio" || /^\/quarta-taglio\/(?!certificati(?:\/|$))/.test(location.pathname);
    }
    return isActive;
  }

  return (
    <aside className="min-h-full border-r border-border bg-[#fbfbf7] px-4 py-5">
      <nav className="sticky top-0 flex flex-col gap-0.5">
        {visibleNavItems.map((item) => {
          if (item.type === "section") {
            return (
              <div className="mt-5 pt-1 first:mt-0 first:pt-0" key={item.key}>
                <div className="px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">{item.label}</div>
              </div>
            );
          }

          if (!item.roles.includes(user?.role)) {
            return null;
          }

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `group relative flex min-h-8 items-center gap-3 rounded-md px-2 py-1.5 text-[13px] font-medium leading-4 transition ${
                  isNavItemActive(item, isActive)
                    ? "bg-slate-100 text-ink"
                    : "text-slate-600 hover:bg-slate-100/70 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => {
                const active = isNavItemActive(item, isActive);

                return (
                  <>
                    {active ? <span className="absolute left-0 h-5 w-0.5 rounded-full bg-accent" /> : null}
                    <span className={`flex w-5 shrink-0 justify-center ${active ? "text-accent" : "text-slate-500"}`}>
                      <SidebarIcon name={item.icon} />
                    </span>
                    <span className="truncate">{item.label}</span>
                  </>
                );
              }}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
