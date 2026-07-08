import { Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";

import { apiRequest } from "./api";
import { useAuth } from "./auth";
import AccessGuard from "../components/common/AccessGuard";
import ProtectedRoute from "../components/common/ProtectedRoute";
import AppShell from "../components/layout/AppShell";
import ChangePasswordPage from "../pages/auth/ChangePasswordPage";
import LoginPage from "../pages/auth/LoginPage";
import SetPasswordPage from "../pages/auth/SetPasswordPage";
import AcquisitionDetailPage from "../pages/acquisition/AcquisitionDetailPage";
import AcquisitionGembaWalkPrintPage from "../pages/acquisition/AcquisitionGembaWalkPrintPage";
import AcquisitionListPage from "../pages/acquisition/AcquisitionListPage";
import AcquisitionManualDdtPage, { AcquisitionManualCertificatePage } from "../pages/acquisition/AcquisitionManualDdtPage";
import AcquisitionSectionPlaceholderPage from "../pages/acquisition/AcquisitionSectionPlaceholderPage";
import AcquisitionUploadPage from "../pages/acquisition/AcquisitionUploadPage";
import AIConfigPage from "../pages/ai/AIConfigPage";
import ClientsPage from "../pages/clients/ClientsPage";
import DashboardPage from "../pages/core/DashboardPage";
import CustomerRequirementsPage from "../pages/customerRequirements/CustomerRequirementsPage";
import DepartmentsPage from "../pages/departments/DepartmentsPage";
import EmailSettingsPage from "../pages/email/EmailSettingsPage";
import IntegrationsPage from "../pages/integrations/IntegrationsPage";
import LogsPage from "../pages/logs/LogsPage";
import SupplierKpiPage from "../pages/kpi/SupplierKpiPage";
import SupplierCalendarPage from "../pages/kpi/SupplierCalendarPage";
import NotesPage from "../pages/notes/NotesPage";
import QualityEvaluationPage from "../pages/quality/QualityEvaluationPage";
import QuartaTaglioCertificatesRegisterPage from "../pages/quartaTaglio/QuartaTaglioCertificatesRegisterPage";
import QuartaTaglioDetailPage from "../pages/quartaTaglio/QuartaTaglioDetailPage";
import QuartaTaglioPage from "../pages/quartaTaglio/QuartaTaglioPage";
import StandardsPage from "../pages/standards/StandardsPage";
import SupplierCodesPage from "../pages/supplierCodes/SupplierCodesPage";
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
    <AccessGuard page="departments">
      <DepartmentsPage />
    </AccessGuard>
  );
}

function UsersRoute() {
  return (
    <AccessGuard page="users">
      <Outlet />
    </AccessGuard>
  );
}

function LogsRoute() {
  return (
    <AccessGuard page="logs">
      <LogsPage />
    </AccessGuard>
  );
}

function IntegrationsRoute() {
  return (
    <AccessGuard page="integrations">
      <IntegrationsPage />
    </AccessGuard>
  );
}

function AIConfigRoute() {
  return (
    <AccessGuard page="ai">
      <AIConfigPage />
    </AccessGuard>
  );
}

function EmailSettingsRoute() {
  return (
    <AccessGuard page="emailSettings">
      <EmailSettingsPage />
    </AccessGuard>
  );
}

function NotesRoute() {
  return (
    <AccessGuard page="notes">
      <NotesPage />
    </AccessGuard>
  );
}

function KpiRoute() {
  return (
    <AccessGuard page="supplierKpi">
      <SupplierKpiPage />
    </AccessGuard>
  );
}

function SupplierCalendarRoute() {
  return (
    <AccessGuard page="supplierCalendar">
      <SupplierCalendarPage />
    </AccessGuard>
  );
}

function ClientsRoute() {
  return (
    <AccessGuard page="clients">
      <ClientsPage />
    </AccessGuard>
  );
}

function CustomerRequirementsRoute() {
  return (
    <AccessGuard page="customerRequirements">
      <CustomerRequirementsPage />
    </AccessGuard>
  );
}

function SupplierCodesRoute() {
  return (
    <AccessGuard page="supplierCodes">
      <SupplierCodesPage />
    </AccessGuard>
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
          <Route path="/dashboard" element={<AccessGuard page="dashboard"><DashboardPage /></AccessGuard>} />
          <Route path="/acquisition" element={<AccessGuard page="acquisition"><AcquisitionListPage /></AccessGuard>} />
          <Route path="/acquisition/gemba-walk/print" element={<AccessGuard page="acquisition"><AcquisitionGembaWalkPrintPage /></AccessGuard>} />
          <Route path="/acquisition/upload" element={<AccessGuard page="acquisitionUpload"><AcquisitionUploadPage /></AccessGuard>} />
          <Route path="/acquisition/manual/ddt" element={<AccessGuard page="acquisitionUpload"><AcquisitionManualDdtPage /></AccessGuard>} />
          <Route path="/acquisition/manual/certificato" element={<AccessGuard page="acquisitionUpload"><AcquisitionManualCertificatePage /></AccessGuard>} />
          <Route path="/acquisition/:rowId/:sectionKey" element={<AccessGuard page="acquisition"><AcquisitionSectionPlaceholderPage /></AccessGuard>} />
          <Route path="/acquisition/:rowId" element={<AccessGuard page="acquisition"><AcquisitionDetailPage /></AccessGuard>} />
          <Route path="/suppliers" element={<AccessGuard page="suppliers"><SuppliersListPage /></AccessGuard>} />
          <Route path="/suppliers/new" element={<Navigate to="/suppliers" replace />} />
          <Route path="/suppliers/:supplierId" element={<AccessGuard page="suppliers"><SupplierDetailPage /></AccessGuard>} />
          <Route path="/clients" element={<ClientsRoute />} />
          <Route path="/departments" element={<DepartmentsRoute />} />
          <Route path="/integrations" element={<IntegrationsRoute />} />
          <Route path="/ai" element={<AIConfigRoute />} />
          <Route path="/email-settings" element={<EmailSettingsRoute />} />
          <Route path="/standards" element={<AccessGuard page="standards"><StandardsPage /></AccessGuard>} />
          <Route path="/customer-requirements" element={<CustomerRequirementsRoute />} />
          <Route path="/supplier-codes" element={<SupplierCodesRoute />} />
          <Route path="/quality-evaluation" element={<AccessGuard page="qualityEvaluation"><QualityEvaluationPage /></AccessGuard>} />
          <Route path="/supplier-kpi" element={<KpiRoute />} />
          <Route path="/supplier-calendar" element={<SupplierCalendarRoute />} />
          <Route path="/quarta-taglio" element={<AccessGuard page="certification"><QuartaTaglioPage /></AccessGuard>} />
          <Route path="/quarta-taglio/certificati" element={<AccessGuard page="certificateRegister"><QuartaTaglioCertificatesRegisterPage /></AccessGuard>} />
          <Route path="/quarta-taglio/:codOdp" element={<AccessGuard page="certification"><QuartaTaglioDetailPage /></AccessGuard>} />
          <Route path="/notes" element={<NotesRoute />} />
          <Route path="/logs" element={<LogsRoute />} />
          <Route path="/users" element={<UsersRoute />}>
            <Route index element={<UsersListPage />} />
            <Route
              path="new"
              element={
                <AccessGuard page="users">
                  <NewUserPage />
                </AccessGuard>
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
