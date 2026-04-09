import { Outlet, useLocation } from "react-router-dom";

import Footer from "./Footer";
import Header from "./Header";
import Sidebar from "./Sidebar";

export default function AppShell() {
  const location = useLocation();
  const isAcquisitionRoute = location.pathname.startsWith("/acquisition");

  return (
    <div className="min-h-screen bg-shell text-ink">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar />
        <div className="flex min-h-screen flex-col">
          <Header />
          <main className="flex-1 bg-gradient-to-b from-shell to-slate-100 p-6">
            <div className={`mx-auto w-full ${isAcquisitionRoute ? "max-w-none" : "max-w-6xl"}`}>
              <Outlet />
            </div>
          </main>
          <Footer />
        </div>
      </div>
    </div>
  );
}
