import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../app/auth";

export default function ProtectedRoute({ allowForcePasswordChange = false }) {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-ink">Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (user?.force_password_change && !allowForcePasswordChange) {
    return <Navigate to="/change-password" replace />;
  }

  return <Outlet />;
}
