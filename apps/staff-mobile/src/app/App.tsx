import { Navigate, Route, Routes } from "react-router-dom";

import { MobileShell } from "../components/MobileShell";
import { ActualsPage } from "../pages/ActualsPage";
import { AvailabilityPage } from "../pages/AvailabilityPage";
import { ExpensesPage } from "../pages/ExpensesPage";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { LoginPage } from "../pages/LoginPage";
import { SchedulePage } from "../pages/SchedulePage";
import { TodayAssignmentsPage } from "../pages/TodayAssignmentsPage";
import { ProtectedRoute } from "../routes/ProtectedRoute";
import { WorkerOnlyRoute } from "../routes/WorkerOnlyRoute";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/403" element={<ForbiddenPage />} />
        <Route element={<WorkerOnlyRoute />}>
          <Route element={<MobileShell />}>
            <Route index element={<Navigate to="/today" replace />} />
            <Route path="/today" element={<TodayAssignmentsPage />} />
            <Route path="/schedule" element={<SchedulePage />} />
            <Route path="/availability" element={<AvailabilityPage />} />
            <Route path="/actuals" element={<ActualsPage />} />
            <Route path="/expenses" element={<ExpensesPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/today" replace />} />
    </Routes>
  );
}