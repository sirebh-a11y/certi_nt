import { Navigate } from "react-router-dom";

import { canAccessPage } from "../../app/access";
import { useAuth } from "../../app/auth";

export default function AccessGuard({ page, children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="px-6 py-8 text-sm text-slate-500">Caricamento autorizzazioni...</div>;
  }

  if (!canAccessPage(user, page)) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
