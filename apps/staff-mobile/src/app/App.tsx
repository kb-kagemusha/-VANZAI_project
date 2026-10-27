import { Navigate, Route, Routes } from "react-router-dom";

import { MobileShell } from "../components/MobileShell";
import { AppDialogHost } from "../lib/appDialog";
import { ActualsPage } from "../pages/ActualsPage";
import { AvailabilityPage } from "../pages/AvailabilityPage";
import { ExpensesPage } from "../pages/ExpensesPage";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { LoginPage } from "../pages/LoginPage";
import { NoticesPage } from "../pages/NoticesPage";
import { PersonalSettingsPage } from "../pages/PersonalSettingsPage";
import { LineScheduleNoticePage } from "../pages/LineScheduleNoticePage";
import { ProtectedRoute } from "../routes/ProtectedRoute";
import { WorkerOnlyRoute } from "../routes/WorkerOnlyRoute";

export function App() {
  return (
    <>
    <AppDialogHost />
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/403" element={<ForbiddenPage />} />
        <Route element={<WorkerOnlyRoute />}>
          <Route element={<MobileShell />}>
            <Route index element={<Navigate to="/availability" replace />} />
            {/* 稼働予定は公式LINEで確認する（DEC-064）。旧URLには案内を出す */}
            <Route path="/today" element={<LineScheduleNoticePage />} />
            <Route path="/schedule" element={<LineScheduleNoticePage />} />
            <Route path="/availability" element={<AvailabilityPage />} />
            <Route path="/settings" element={<PersonalSettingsPage />} />
            <Route path="/actuals" element={<ActualsPage />} />
            <Route path="/expenses" element={<ExpensesPage />} />
            <Route path="/notices" element={<NoticesPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/availability" replace />} />
    </Routes>
    </>
  );
}