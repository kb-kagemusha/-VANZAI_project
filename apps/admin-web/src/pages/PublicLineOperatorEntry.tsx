import { PublicLineOperatorRegistrationPage } from "./PublicLineOperatorRegistrationPage";
import { PublicLineOperatorPortalPage } from "./PublicLineOperatorPortalPage";

export function operatorMode(): string {
  const params = new URLSearchParams(window.location.search);
  const state = params.get("liff.state") ?? "";
  return params.get("m") ?? new URLSearchParams(state.includes("?") ? state.slice(state.indexOf("?") + 1) : state).get("m") ?? "";
}

export function PublicLineOperatorEntry() {
  return ["wake", "today", "calendar", "orders", "availability", "profile"].includes(operatorMode()) ? <PublicLineOperatorPortalPage /> : <PublicLineOperatorRegistrationPage />;
}
