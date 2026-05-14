import { Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";

import { apiRequest } from "./api";
import { useAuth } from "./auth";
import ProtectedRoute from "../components/common/ProtectedRoute";
import RoleGuard from "../components/common/RoleGuard";
import AppShell from "../components/layout/AppShell";
import ChangePasswordPage from "../pages/auth/ChangePasswordPage";
import LoginPage from "../pages/auth/LoginPage";
import SetPasswordPage from "../pages/auth/SetPasswordPage";
import AcquisitionDetailPage from "../pages/acquisition/AcquisitionDetailPage";
import AcquisitionListPage from "../pages/acquisition/AcquisitionListPage";
import AcquisitionManualDdtPage, { AcquisitionManualCertificatePage } from "../pages/acquisition/AcquisitionManualDdtPage";
import AcquisitionSectionPlaceholderPage from "../pages/acquisition/AcquisitionSectionPlaceholderPage";
import AcquisitionUploadPage from "../pages/acquisition/AcquisitionUploadPage";
import AIConfigPage from "../pages/ai/AIConfigPage";
import DashboardPage from "../pages/core/DashboardPage";
import PlaceholderPage from "../pages/core/PlaceholderPage";
import DepartmentsPage from "../pages/departments/DepartmentsPage";
import IntegrationsPage from "../pages/integrations/IntegrationsPage";
import LogsPage from "../pages/logs/LogsPage";
import SupplierKpiPage from "../pages/kpi/SupplierKpiPage";
import NotesPage from "../pages/notes/NotesPage";
import QualityEvaluationPage from "../pages/quality/QualityEvaluationPage";
import QuartaTaglioCertificatesRegisterPage from "../pages/quartaTaglio/QuartaTaglioCertificatesRegisterPage";
import QuartaTaglioDetailPage from "../pages/quartaTaglio/QuartaTaglioDetailPage";
import QuartaTaglioPage from "../pages/quartaTaglio/QuartaTaglioPage";
import StandardsPage from "../pages/standards/StandardsPage";
import NewSupplierPage from "../pages/suppliers/NewSupplierPage";
import SupplierDetailPage from "../pages/suppliers/SupplierDetailPage";
import SuppliersListPage from "../pages/suppliers/SuppliersListPage";
import NewUserPage from "../pages/users/NewUserPage";
import UserDetailPage from "../pages/users/UserDetailPage";
import UsersListPage from "../pages/users/UsersListPage";

function AppShellRoute() {
  return <AppShell />;
}

function UserDetailRoute() {
  const { token, user } = useAuth();
  const { userId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    apiRequest(`/users/${userId}`, {}, token)
      .then((response) => {
        if (!ignore) {
          setData(response);
        }
      })
      .catch((requestError) => {
        if (!ignore) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [token, userId]);

  return (
    <UserDetailPage
      currentUser={user}
      error={error}
      loading={loading}
      onBack={() => navigate(user?.role === "user" ? "/dashboard" : "/users")}
      userData={data}
    />
  );
}

function DepartmentsRoute() {
  return (
    <RoleGuard allowedRoles={["admin"]}>
      <DepartmentsPage />
    </RoleGuard>
  );
}

function UsersRoute() {
  return (
    <RoleGuard allowedRoles={["manager", "admin"]}>
      <Outlet />
    </RoleGuard>
  );
}

function LogsRoute() {
  return (
    <RoleGuard allowedRoles={["manager", "admin"]}>
      <LogsPage />
    </RoleGuard>
  );
}

function IntegrationsRoute() {
  return (
    <RoleGuard allowedRoles={["admin"]}>
      <IntegrationsPage />
    </RoleGuard>
  );
}

function AIConfigRoute() {
  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AIConfigPage />
    </RoleGuard>
  );
}

function NotesRoute() {
  return <NotesPage />;
}

function KpiRoute() {
  return <SupplierKpiPage />;
}

function ClientsRoute() {
  return (
    <PlaceholderPage
      eyebrow="Anagrafica"
      title="Clienti"
      description="Area futura per gestire l'anagrafica clienti e i dati collegati ai flussi di certificazione."
    />
  );
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/set-password" element={<SetPasswordPage />} />

      <Route element={<ProtectedRoute allowForcePasswordChange />}>
        <Route element={<AppShellRoute />}>
          <Route path="/change-password" element={<ChangePasswordPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShellRoute />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/acquisition" element={<AcquisitionListPage />} />
          <Route path="/acquisition/upload" element={<AcquisitionUploadPage />} />
          <Route path="/acquisition/manual/ddt" element={<AcquisitionManualDdtPage />} />
          <Route path="/acquisition/manual/certificato" element={<AcquisitionManualCertificatePage />} />
          <Route path="/acquisition/:rowId/:sectionKey" element={<AcquisitionSectionPlaceholderPage />} />
          <Route path="/acquisition/:rowId" element={<AcquisitionDetailPage />} />
          <Route path="/suppliers" element={<SuppliersListPage />} />
          <Route path="/suppliers/new" element={<NewSupplierPage />} />
          <Route path="/suppliers/:supplierId" element={<SupplierDetailPage />} />
          <Route path="/clients" element={<ClientsRoute />} />
          <Route path="/departments" element={<DepartmentsRoute />} />
          <Route path="/integrations" element={<IntegrationsRoute />} />
          <Route path="/ai" element={<AIConfigRoute />} />
          <Route path="/standards" element={<StandardsPage />} />
          <Route path="/quality-evaluation" element={<QualityEvaluationPage />} />
          <Route path="/supplier-kpi" element={<KpiRoute />} />
          <Route path="/quarta-taglio" element={<QuartaTaglioPage />} />
          <Route path="/quarta-taglio/certificati" element={<QuartaTaglioCertificatesRegisterPage />} />
          <Route path="/quarta-taglio/:codOdp" element={<QuartaTaglioDetailPage />} />
          <Route path="/notes" element={<NotesRoute />} />
          <Route path="/logs" element={<LogsRoute />} />
          <Route path="/users" element={<UsersRoute />}>
            <Route index element={<UsersListPage />} />
            <Route
              path="new"
              element={
                <RoleGuard allowedRoles={["admin"]}>
                  <NewUserPage />
                </RoleGuard>
              }
            />
            <Route path=":userId" element={<UserDetailRoute />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
