export const MANAGEMENT_ROLES = ["総合管理", "支払い経理", "収益管理", "現場管理", "基礎管理"] as const;
export type ManagementRole = typeof MANAGEMENT_ROLES[number];
export interface OperatorStaffWrite {
  name: string; phone: string | null; email: string | null; can_drive: boolean | null; smoking_area_ok: boolean | null;
  emergency_contact_name: string | null; emergency_contact_phone: string | null; emergency_contact_relationship: string | null;
  management_roles: ManagementRole[]; is_active: boolean; notes: string | null; profile_revision?: number;
}
export interface OperatorStaffItem extends OperatorStaffWrite {
  id: string; profile_revision: number; line_linked: boolean; line_display_name: string | null; line_linked_at: string | null;
}

export interface OperatorInvitation { request_id: string; expires_at: string; url: string }
export interface OperatorRegistrationReview {
  request_id: string; status: string; name: string; phone: string; line_display_name: string;
  staff_id: string | null;
  candidates: { id: string; name: string; phone: string | null; profile_revision: number }[];
}
