import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { DASHBOARD_ROLES } from "../lib/auth/permissions";
import { CsvImportPage } from "../pages/CsvImportPage";
import { ActualsPage } from "../pages/ActualsPage";
import { AssignmentResponsesPage } from "../pages/AssignmentResponsesPage";
import { AuditLogsPage } from "../pages/AuditLogsPage";
import { AssignmentsPage } from "../pages/AssignmentsPage";
import { DashboardPage } from "../pages/DashboardPage";
import { ExpensesPage } from "../pages/ExpensesPage";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { InvoicesPage } from "../pages/InvoicesPage";
import { LoginPage } from "../pages/LoginPage";
import { MasterDataPage } from "../pages/MasterDataPage";
import { PayoutsPage } from "../pages/PayoutsPage";
import { PriceManagementPage } from "../pages/PriceManagementPage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { ShiftSlotsPage } from "../pages/ShiftSlotsPage";
import { WorkersPage } from "../pages/WorkersPage";
import { ChangePasswordPage } from "../pages/ChangePasswordPage";
import { PermissionRoute } from "../routes/PermissionRoute";
import { ProtectedRoute } from "../routes/ProtectedRoute";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/403" element={<ForbiddenPage />} />
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <PermissionRoute allowedRoles={DASHBOARD_ROLES}>
                <DashboardPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/operations/csv-import"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "site_manager"]}>
                <CsvImportPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/operations/actuals"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting", "site_manager"]}>
                <ActualsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/operations/assignments"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting", "site_manager"]}>
                <AssignmentsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/operations/assignment-responses"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting", "site_manager"]}>
                <AssignmentResponsesPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/operations/projects"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting", "site_manager"]}>
                <ProjectsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/operations/shift-slots"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting", "site_manager"]}>
                <ShiftSlotsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/billing/invoices"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting"]}>
                <InvoicesPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/billing/payouts"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting"]}>
                <PayoutsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/billing/expenses"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting"]}>
                <ExpensesPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/masters/prices"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting"]}>
                <PriceManagementPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/masters/workers"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting", "site_manager"]}>
                <WorkersPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/masters/data"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting", "site_manager"]}>
                <MasterDataPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/audit-logs"
            element={
              <PermissionRoute allowedRoles={["admin", "ops", "accounting"]}>
                <AuditLogsPage />
              </PermissionRoute>
            }
          />
          <Route path="/account/change-password" element={<ChangePasswordPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}