import { Navigate } from "react-router-dom";

import { canAccessPage } from "../../app/access";
import { useAuth } from "../../app/auth";

export default function AccessGuard({ page, children }) {
  const { user } = useAuth();

  if (!canAccessPage(user, page)) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
