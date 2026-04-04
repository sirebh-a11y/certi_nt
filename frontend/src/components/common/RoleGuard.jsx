import { Navigate } from "react-router-dom";

import { useAuth } from "../../app/auth";

export default function RoleGuard({ allowedRoles, children }) {
  const { user } = useAuth();

  if (!user || !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
