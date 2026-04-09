import { NavLink } from "react-router-dom";

import { useAuth } from "../../app/auth";

const navItems = [
  { label: "Dashboard", to: "/dashboard", roles: ["user", "manager", "admin"] },
  { type: "divider" },
  { label: "Incoming Quality", to: "/acquisition", roles: ["user", "manager", "admin"] },
  { label: "Anagrafica Fornitori", to: "/suppliers", roles: ["user", "manager", "admin"] },
  { label: "Utenti", to: "/users", roles: ["manager", "admin"] },
  { label: "Reparti", to: "/departments", roles: ["admin"] },
  { label: "Log", to: "/logs", roles: ["manager", "admin"] },
];

export default function Sidebar() {
  const { user } = useAuth();

  return (
    <aside className="border-r border-border bg-panel px-4 py-6">
      <nav className="sticky top-0 flex flex-col gap-2">
        {navItems.map((item) => {
          if (item.type === "divider") {
            return <div key="divider" className="my-2 border-t border-border" />;
          }

          if (!item.roles.includes(user?.role)) {
            return null;
          }

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-xl px-4 py-3 text-sm font-medium transition ${
                  isActive ? "bg-accent text-white" : "text-slate-600 hover:bg-slate-100 hover:text-ink"
                }`
              }
            >
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
