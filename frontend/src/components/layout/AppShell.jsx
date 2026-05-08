import { Outlet, useLocation } from "react-router-dom";

import Footer from "./Footer";
import Header from "./Header";
import Sidebar from "./Sidebar";

export default function AppShell() {
  const location = useLocation();
  const isAcquisitionRoute = location.pathname.startsWith("/acquisition");
  const isWideRoute = isAcquisitionRoute || location.pathname.startsWith("/quality-evaluation");

  return (
    <div className="h-screen overflow-hidden bg-shell text-ink">
      <div className="grid h-screen grid-cols-1 overflow-hidden lg:grid-cols-[220px_minmax(0,1fr)]">
        <div className="h-screen overflow-y-auto overflow-x-hidden">
          <Sidebar />
        </div>
        <div className="flex h-screen min-h-0 flex-col overflow-hidden">
          <Header />
          <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden bg-gradient-to-b from-shell to-slate-100 p-6">
            <div className={`mx-auto w-full ${isWideRoute ? "max-w-none" : "max-w-6xl"}`}>
              <Outlet />
            </div>
          </main>
          <Footer />
        </div>
      </div>
    </div>
  );
}
