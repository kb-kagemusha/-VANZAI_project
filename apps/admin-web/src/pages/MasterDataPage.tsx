import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { ClientCompanyEditor } from "../components/ClientCompanyEditor";
import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { WorkerTagList, WorkerTagPicker } from "../components/WorkerTags";
import { ProfileDialog } from "../components/ProfileDialog";
import { useAuth } from "../lib/auth/auth-context";
import {
  ApiError,
  createClient,
  createProjectType,
  createRole,
  createSite,
  createSupplierBankAccount,
  createSupplier,
  createVanzaiStaff,
  createWorker,
  getClients,
  getProjectTypeTree,
  getProjectTypes,
  getRoles,
  getSites,
  getSupplierBankAccounts,
  getSuppliers,
  getVanzaiStaff,
  getWorkerTags,
  getWorkerEditGuard,
  getWorkers,
  updateSupplierBankAccount,
  updateSupplier,
  updateVanzaiStaff,
  updateWorker,
} from "../lib/api/client";
import { formatDate, formatMaskedAccountNumber } from "../lib/formatters";
import { workerEditFieldsFromGuard } from "../lib/workerEditForm";
import type {
  ClientCreateRequest,
  ClientListItem,
  ProjectTypeCreateRequest,
  RoleCreateRequest,
  SiteCreateRequest,
  SupplierCreateRequest,
  SupplierBankAccountCreateRequest,
  SupplierBankAccountItem,
  SupplierListItem,
  SupplierUpdateRequest,
  ProjectTypeTreeItem,
  VanzaiStaffItem,
  VanzaiStaffCreateRequest,
  VanzaiStaffUpdateRequest,
  WorkerCreateRequest,
  WorkerEditGuardResponse,
  WorkerListItem,
  WorkerUpdateRequest,
} from "../types/api";

import { lookupPostalAddress, normalizePostalCode } from "../lib/postalAddress";

const PAGE_SIZE = 20;
const VANZAI_STAFF_ROLE_OPTIONS = ["プレイングマネージャー", "事務", "全体統括", "全体統括責任者"];
const PLAYING_MANAGER_FEE_TYPE_OPTIONS = [
  { value: "subordinate_man_days", label: "配下人工×1,000円" },
  { value: "fixed_amount", label: "固定額" },
] as const;

function flattenProjectTypeOptions(nodes: ProjectTypeTreeItem[], depth = 0): Array<{ id: string; label: string }> {
  const rows: Array<{ id: string; label: string }> = [];
  for (const node of nodes) {
    rows.push({ id: node.id, label: `${"  ".repeat(depth)}${node.name}` });
    rows.push(...flattenProjectTypeOptions(node.children, depth + 1));
  }
  return rows;
}

type MasterView = "workers" | "suppliers" | "clients" | "sites" | "project_types" | "roles" | "vanzai_staff";

type CreateMasterVariables =
  | { view: "workers"; body: WorkerCreateRequest }
  | { view: "suppliers"; body: SupplierCreateRequest }
  | { view: "clients"; body: ClientCreateRequest }
  | { view: "sites"; body: SiteCreateRequest }
  | { view: "project_types"; body: ProjectTypeCreateRequest }
  | { view: "roles"; body: RoleCreateRequest }
  | { view: "vanzai_staff"; body: VanzaiStaffCreateRequest };

type UpdateMasterVariables =
  | { view: "workers"; id: string; body: WorkerUpdateRequest }
  | { view: "suppliers"; id: string; body: SupplierUpdateRequest }
  | { view: "vanzai_staff"; id: string; body: VanzaiStaffUpdateRequest };

const VIEW_LABELS: Record<MasterView, string> = {
  workers: "稼働者",
  suppliers: "下請け",
  clients: "クライアント",
  sites: "現場",
  project_types: "案件種別",
  roles: "役割",
  vanzai_staff: "VANZAI担当者",
};

const VIEW_COLORS: Record<MasterView, string> = { workers: "#2563eb", suppliers: "#c2410c", clients: "#7e22ce", sites: "#0f766e", project_types: "#b45309", roles: "#be123c", vanzai_staff: "#64748b" };

function validateEffectiveRange(effectiveFrom: string, effectiveUntil: string): void {
  if (effectiveUntil && effectiveUntil < effectiveFrom) {
    throw new ApiError(400, "有効終了日は有効開始日以降を指定してください");
  }
}

export function MasterDataPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [view, setView] = useState<MasterView>("workers");
  const [createOpen, setCreateOpen] = useState(false);
  const [extraContacts, setExtraContacts] = useState<Array<{ id: string; name: string; role: string; phone: string; email: string }>>([]);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [isActive, setIsActive] = useState("");
  const [createName, setCreateName] = useState("");
  const [createCode, setCreateCode] = useState("");
  const [createEmail, setCreateEmail] = useState("");
  const [createPhone, setCreatePhone] = useState("");
  const [createSupplierId, setCreateSupplierId] = useState("");
  const [createContactRole, setCreateContactRole] = useState("");
  const [createPostalCode, setCreatePostalCode] = useState("");
  const [postalMessage, setPostalMessage] = useState("");
  const [postalChoices, setPostalChoices] = useState<string[]>([]);
  const lastAutoAddress = useRef("");
  const [createContactName, setCreateContactName] = useState("");
  const [createContactEmail, setCreateContactEmail] = useState("");
  const [createContactPhone, setCreateContactPhone] = useState("");
  const [createAddress, setCreateAddress] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createProjectTypeLevel, setCreateProjectTypeLevel] = useState("minor");
  const [createProjectTypeParentId, setCreateProjectTypeParentId] = useState("");
  const [createTermsDays, setCreateTermsDays] = useState("70");
  const [createDefaultDailyPrice, setCreateDefaultDailyPrice] = useState("");
  const [createVanzaiStaffRole, setCreateVanzaiStaffRole] = useState("");
  const [createLinkedWorkerId, setCreateLinkedWorkerId] = useState("");
  const [createPlayingManagerFeeType, setCreatePlayingManagerFeeType] = useState("subordinate_man_days");
  const [createPlayingManagerFixedFee, setCreatePlayingManagerFixedFee] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);
  const [createTags, setCreateTags] = useState<string[]>([]);
  const [selectedWorker, setSelectedWorker] = useState<WorkerListItem | null>(null);
  const [selectedSupplier, setSelectedSupplier] = useState<SupplierListItem | null>(null);
  const [selectedVanzaiStaff, setSelectedVanzaiStaff] = useState<VanzaiStaffItem | null>(null);
  const [editingClient, setEditingClient] = useState<ClientListItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editSupplierId, setEditSupplierId] = useState("");
  const [editContactPhone, setEditContactPhone] = useState("");
  const [editTermsDays, setEditTermsDays] = useState("70");
  const [editDefaultDailyPrice, setEditDefaultDailyPrice] = useState("");
  const [editVanzaiStaffRole, setEditVanzaiStaffRole] = useState("");
  const [editLinkedWorkerId, setEditLinkedWorkerId] = useState("");
  const [editPlayingManagerFeeType, setEditPlayingManagerFeeType] = useState("subordinate_man_days");
  const [editPlayingManagerFixedFee, setEditPlayingManagerFixedFee] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [editTags, setEditTags] = useState<string[]>([]);
  const [formError, setFormError] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [editError, setEditError] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const [editGuard, setEditGuard] = useState("");
  const [editNeedsReload, setEditNeedsReload] = useState(false);
  const [supplierBankBankName, setSupplierBankBankName] = useState("");
  const [supplierBankBranchName, setSupplierBankBranchName] = useState("");
  const [supplierBankBranchCode, setSupplierBankBranchCode] = useState("");
  const [supplierBankAccountType, setSupplierBankAccountType] = useState("普通");
  const [supplierBankAccountNumber, setSupplierBankAccountNumber] = useState("");
  const [supplierBankHolderKana, setSupplierBankHolderKana] = useState("");
  const [supplierBankEffectiveFrom, setSupplierBankEffectiveFrom] = useState("");
  const [supplierBankEffectiveUntil, setSupplierBankEffectiveUntil] = useState("");
  const [supplierBankIsPrimary, setSupplierBankIsPrimary] = useState(false);
  const [supplierBankFormError, setSupplierBankFormError] = useState("");
  const [supplierBankFormMessage, setSupplierBankFormMessage] = useState("");
  const [selectedSupplierBankAccount, setSelectedSupplierBankAccount] = useState<SupplierBankAccountItem | null>(null);
  const [supplierEditBankName, setSupplierEditBankName] = useState("");
  const [supplierEditBranchName, setSupplierEditBranchName] = useState("");
  const [supplierEditBranchCode, setSupplierEditBranchCode] = useState("");
  const [supplierEditAccountType, setSupplierEditAccountType] = useState("普通");
  const [supplierEditAccountNumber, setSupplierEditAccountNumber] = useState("");
  const [supplierEditHolderKana, setSupplierEditHolderKana] = useState("");
  const [supplierEditEffectiveFrom, setSupplierEditEffectiveFrom] = useState("");
  const [supplierEditEffectiveUntil, setSupplierEditEffectiveUntil] = useState("");
  const [supplierEditIsPrimary, setSupplierEditIsPrimary] = useState(false);
  const [supplierBankEditError, setSupplierBankEditError] = useState("");
  const [supplierBankEditMessage, setSupplierBankEditMessage] = useState("");

  useEffect(() => {
    setPostalChoices([]);
    setPostalMessage("");
    if (view !== "clients" || !createOpen) return;
    const postal = normalizePostalCode(createPostalCode);
    if (!/^[0-9]{7}$/.test(postal)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const choices = await lookupPostalAddress(postal, controller.signal);
        if (controller.signal.aborted) return;
        const addresses = choices.map((choice) => choice.prefecture + choice.address);
        if (addresses.length === 1) {
          const previous = lastAutoAddress.current;
          const address = addresses[0];
          setCreateAddress((current) => !current || current === previous ? address : current);
          lastAutoAddress.current = address;
          setPostalMessage("住所候補を取得しました。番地・建物名を確認・入力してください。");
        } else if (addresses.length > 1) {
          setPostalChoices(addresses);
          setPostalMessage("住所候補を選択してください。");
        } else setPostalMessage("住所が見つかりませんでした。住所を直接入力してください。");
      } catch {
        if (!controller.signal.aborted) setPostalMessage("住所を取得できませんでした。住所を直接入力してください。");
      }
    }, 400);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [createPostalCode, view, createOpen]);

  function resetCreateForm() {
    setExtraContacts([]);
    setCreateName("");
    setCreateCode("");
    setCreateEmail("");
    setCreatePhone("");
    setCreateSupplierId("");
    setCreateContactRole("");
    setCreatePostalCode("");
    lastAutoAddress.current = "";
    setCreateContactName("");
    setCreateContactEmail("");
    setCreateContactPhone("");
    setCreateAddress("");
    setCreateDescription("");
    setCreateProjectTypeLevel("minor");
    setCreateProjectTypeParentId("");
    setCreateTermsDays("70");
    setCreateDefaultDailyPrice("");
    setCreateVanzaiStaffRole("");
    setCreateLinkedWorkerId("");
    setCreatePlayingManagerFeeType("subordinate_man_days");
    setCreatePlayingManagerFixedFee("");
    setCreateNotes("");
    setCreateIsActive(true);
    setCreateTags([]);
    setFormError("");
    setFormMessage("");
  }

  function clearEditor() {
    setSelectedWorker(null);
    setEditGuard("");
    setEditNeedsReload(false);
    setSelectedSupplier(null);
    setSelectedVanzaiStaff(null);
    setEditingClient(null);
    setEditName("");
    setEditEmail("");
    setEditPhone("");
    setEditSupplierId("");
    setEditContactPhone("");
    setEditTermsDays("70");
    setEditDefaultDailyPrice("");
    setEditVanzaiStaffRole("");
    setEditLinkedWorkerId("");
    setEditPlayingManagerFeeType("subordinate_man_days");
    setEditPlayingManagerFixedFee("");
    setEditNotes("");
    setEditIsActive(true);
    setEditTags([]);
    setEditError("");
    setEditMessage("");
    setSupplierBankBankName("");
    setSupplierBankBranchName("");
    setSupplierBankBranchCode("");
    setSupplierBankAccountType("普通");
    setSupplierBankAccountNumber("");
    setSupplierBankHolderKana("");
    setSupplierBankEffectiveFrom("");
    setSupplierBankEffectiveUntil("");
    setSupplierBankIsPrimary(false);
    setSupplierBankFormError("");
    setSupplierBankFormMessage("");
    setSelectedSupplierBankAccount(null);
    setSupplierEditBankName("");
    setSupplierEditBranchName("");
    setSupplierEditBranchCode("");
    setSupplierEditAccountType("普通");
    setSupplierEditAccountNumber("");
    setSupplierEditHolderKana("");
    setSupplierEditEffectiveFrom("");
    setSupplierEditEffectiveUntil("");
    setSupplierEditIsPrimary(false);
    setSupplierBankEditError("");
    setSupplierBankEditMessage("");
  }

  function handleViewChange(next: MasterView) {
    setCreateOpen(false);
    setView(next);
    setPage(0);
    setSearch("");
    setIsActive("");
    resetCreateForm();
    clearEditor();
  }

  function applyWorkerEdit(fresh: WorkerEditGuardResponse) {
    const fields = workerEditFieldsFromGuard(fresh);
    setEditGuard(fresh.edit_guard);
    setEditNeedsReload(false);
    setSelectedWorker(fresh.worker);
    setEditName(fields.name);
    setEditEmail(fields.email);
    setEditPhone(fields.phone);
    setEditSupplierId(fields.supplierId);
    setEditNotes(fields.notes);
    setEditIsActive(fields.isActive);
    setEditTags(fields.tags);
  }

  async function openWorkerEditor(worker: WorkerListItem) {
    setEditError("");
    setEditMessage("");
    try {
      const fresh = await getWorkerEditGuard(worker.id);
      setSelectedSupplier(null);
      setSelectedVanzaiStaff(null);
      applyWorkerEdit(fresh);
    } catch (error) {
      setEditError(error instanceof ApiError ? error.message : "最新の稼働者を読み込めませんでした");
    }
  }

  function openSupplierEditor(supplier: SupplierListItem) {
    setSelectedWorker(null);
    setSelectedVanzaiStaff(null);
    setSelectedSupplier(supplier);
    setEditName(supplier.name);
    setEditEmail(supplier.contact_email ?? "");
    setEditContactPhone(supplier.contact_phone ?? "");
    setEditTermsDays(String(supplier.payout_terms_days));
    setEditDefaultDailyPrice(supplier.default_daily_price ?? "");
    setEditNotes(supplier.notes ?? "");
    setEditIsActive(supplier.is_active);
    setEditError("");
    setEditMessage("");
    setSelectedSupplierBankAccount(null);
    setSupplierBankEditError("");
    setSupplierBankEditMessage("");
  }

  function openSupplierBankEditor(account: SupplierBankAccountItem) {
    setSelectedSupplierBankAccount(account);
    setSupplierEditBankName(account.bank_name);
    setSupplierEditBranchName(account.branch_name);
    setSupplierEditBranchCode(account.branch_code ?? "");
    setSupplierEditAccountType(account.account_type);
    setSupplierEditAccountNumber(account.account_number);
    setSupplierEditHolderKana(account.account_holder_kana);
    setSupplierEditEffectiveFrom(account.effective_from);
    setSupplierEditEffectiveUntil(account.effective_until ?? "");
    setSupplierEditIsPrimary(account.is_primary);
    setSupplierBankEditError("");
    setSupplierBankEditMessage("");
  }

  const commonParams = {
    search: search || undefined,
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  };

  const workerTagsQuery = useQuery({
    queryKey: ["worker-tags"],
    queryFn: getWorkerTags,
    enabled: view === "workers",
  });
  const workerTagOptions = workerTagsQuery.data?.items ?? [];

  const workersQuery = useQuery({
    queryKey: ["workers-page", search, isActive, page],
    queryFn: () => getWorkers({ ...commonParams, is_active: isActive === "" ? undefined : isActive === "true" }),
    enabled: view === "workers",
  });

  const suppliersQuery = useQuery({
    queryKey: ["suppliers-page", search, isActive, page],
    queryFn: () => getSuppliers({ ...commonParams, is_active: isActive === "" ? undefined : isActive === "true" }),
    enabled: view === "suppliers",
  });

  const supplierOptionsQuery = useQuery({
    queryKey: ["suppliers-master-options"],
    queryFn: () => getSuppliers({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
    enabled: user?.role === "admin",
  });

  const workerOptionsQuery = useQuery({
    queryKey: ["workers-master-options"],
    queryFn: () => getWorkers({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
    enabled: user?.role === "admin",
  });

  const clientsQuery = useQuery({
    queryKey: ["clients-page", search, page],
    queryFn: () => getClients(commonParams),
    enabled: view === "clients",
  });

  const sitesQuery = useQuery({
    queryKey: ["sites-page", search, page],
    queryFn: () => getSites(commonParams),
    enabled: view === "sites",
  });

  const projectTypesQuery = useQuery({
    queryKey: ["project-types-page", search, page],
    queryFn: () => getProjectTypes(commonParams),
    enabled: view === "project_types",
  });

  const projectTypeTreeQuery = useQuery({
    queryKey: ["project-types-tree"],
    queryFn: () => getProjectTypeTree(),
    enabled: user?.role === "admin",
  });

  const projectTypeOptions = flattenProjectTypeOptions(projectTypeTreeQuery.data?.items ?? []);

  const rolesQuery = useQuery({
    queryKey: ["roles-page", search, page],
    queryFn: () => getRoles(commonParams),
    enabled: view === "roles",
  });

  const vanzaiStaffQuery = useQuery({
    queryKey: ["vanzai-staff-page", search, isActive, page],
    queryFn: () => getVanzaiStaff({ ...commonParams, is_active: isActive === "" ? undefined : isActive === "true" }),
    enabled: view === "vanzai_staff",
  });

  const supplierBankAccountsQuery = useQuery({
    queryKey: ["supplier-bank-accounts", selectedSupplier?.id],
    queryFn: () => getSupplierBankAccounts(selectedSupplier!.id),
    enabled: Boolean(selectedSupplier),
  });

  const createSupplierBankAccountMutation = useMutation({
    mutationFn: (body: SupplierBankAccountCreateRequest) => {
      validateEffectiveRange(body.effective_from, body.effective_until ?? "");
      return createSupplierBankAccount(selectedSupplier!.id, body);
    },
    onSuccess: async () => {
      setSupplierBankFormError("");
      setSupplierBankFormMessage("口座を登録しました");
      setSupplierBankBankName("");
      setSupplierBankBranchName("");
      setSupplierBankBranchCode("");
      setSupplierBankAccountType("普通");
      setSupplierBankAccountNumber("");
      setSupplierBankHolderKana("");
      setSupplierBankEffectiveFrom("");
      setSupplierBankEffectiveUntil("");
      setSupplierBankIsPrimary(false);
      await queryClient.invalidateQueries({ queryKey: ["supplier-bank-accounts", selectedSupplier?.id] });
    },
    onError: (error: unknown) => {
      setSupplierBankFormMessage("");
      setSupplierBankFormError(error instanceof ApiError ? error.message : "口座登録に失敗しました");
    },
  });

  const updateSupplierBankAccountMutation = useMutation({
    mutationFn: () => {
      if (!selectedSupplier || !selectedSupplierBankAccount) {
        throw new Error("更新対象の口座を選択してください");
      }
      validateEffectiveRange(supplierEditEffectiveFrom, supplierEditEffectiveUntil);
      return updateSupplierBankAccount(selectedSupplier.id, selectedSupplierBankAccount.id, {
        bank_name: supplierEditBankName,
        branch_name: supplierEditBranchName,
        branch_code: supplierEditBranchCode || null,
        account_type: supplierEditAccountType,
        account_number: supplierEditAccountNumber,
        account_holder_kana: supplierEditHolderKana,
        transfer_destination_name: null,
        effective_from: supplierEditEffectiveFrom,
        effective_until: supplierEditEffectiveUntil || null,
        is_primary: supplierEditIsPrimary,
      });
    },
    onSuccess: async () => {
      setSupplierBankEditError("");
      setSupplierBankEditMessage("口座を更新しました");
      await queryClient.invalidateQueries({ queryKey: ["supplier-bank-accounts", selectedSupplier?.id] });
    },
    onError: (error: unknown) => {
      setSupplierBankEditMessage("");
      setSupplierBankEditError(error instanceof ApiError ? error.message : "口座更新に失敗しました");
    },
  });

  const activeQuery =
    view === "workers"
      ? workersQuery
      : view === "suppliers"
        ? suppliersQuery
        : view === "clients"
          ? clientsQuery
          : view === "sites"
            ? sitesQuery
            : view === "project_types"
              ? projectTypesQuery
              : view === "vanzai_staff"
                ? vanzaiStaffQuery
                : rolesQuery;

  const createMutation = useMutation<unknown, unknown, CreateMasterVariables>({
    mutationFn: async (variables) => {
      switch (variables.view) {
        case "workers":
          return createWorker(variables.body);
        case "suppliers":
          return createSupplier(variables.body);
        case "clients":
          return createClient(variables.body);
        case "sites":
          return createSite(variables.body);
        case "project_types":
          return createProjectType(variables.body);
        case "roles":
          return createRole(variables.body);
        case "vanzai_staff":
          return createVanzaiStaff(variables.body);
      }
    },
    onSuccess: async (_, variables) => {
      resetCreateForm();
      setCreateOpen(false);
      setPage(0);
      setFormMessage(`${VIEW_LABELS[variables.view]}を作成しました`);

      await queryClient.invalidateQueries({ queryKey: [`${variables.view === "project_types" ? "project-types" : variables.view === "vanzai_staff" ? "vanzai-staff" : variables.view}-page`] });
      if (variables.view === "workers" || variables.view === "suppliers") {
        await queryClient.invalidateQueries({ queryKey: ["suppliers-master-options"] });
      }
      if (variables.view === "workers") {
        await queryClient.invalidateQueries({ queryKey: ["workers-master-options"] });
      }
      if (variables.view === "clients") {
        await queryClient.invalidateQueries({ queryKey: ["clients-project-form"] });
        await queryClient.invalidateQueries({ queryKey: ["order-source-clients"] });
      }
      if (variables.view === "sites") {
        await queryClient.invalidateQueries({ queryKey: ["sites-project-form"] });
      }
      if (variables.view === "project_types") {
        await queryClient.invalidateQueries({ queryKey: ["project-types-project-form"] });
        await queryClient.invalidateQueries({ queryKey: ["project-types-tree"] });
      }
      if (variables.view === "roles") {
        await queryClient.invalidateQueries({ queryKey: ["roles-page"] });
      }
    },
    onError: (error: unknown) => {
      setFormMessage("");
      setFormError(error instanceof ApiError ? error.message : "マスタ作成に失敗しました");
    },
  });

  const updateMutation = useMutation<unknown, unknown, UpdateMasterVariables>({
    mutationFn: async (variables) => {
      switch (variables.view) {
        case "workers":
          return updateWorker(variables.id, variables.body);
        case "suppliers":
          return updateSupplier(variables.id, variables.body);
        case "vanzai_staff":
          return updateVanzaiStaff(variables.id, variables.body);
      }
    },
    onSuccess: async (_, variables) => {
      setEditError("");
      setEditNeedsReload(false);
      setEditMessage(`${VIEW_LABELS[variables.view]}を更新しました`);
      const qKey = variables.view === "vanzai_staff" ? "vanzai-staff-page" : `${variables.view}-page`;
      await queryClient.invalidateQueries({ queryKey: [qKey] });
      if (variables.view === "workers" || variables.view === "suppliers") {
        await queryClient.invalidateQueries({ queryKey: ["suppliers-master-options"] });
      }
      if (variables.view === "workers") {
        await queryClient.invalidateQueries({ queryKey: ["workers-master-options"] });
        const fresh = await getWorkerEditGuard(variables.id);
        applyWorkerEdit(fresh);
      }
    },
    onError: (error: unknown) => {
      setEditMessage("");
      setEditNeedsReload(error instanceof ApiError && error.status === 409);
      setEditError(error instanceof ApiError ? error.message : "更新に失敗しました");
    },
  });

  function handleCreate() {
    if (user?.role !== "admin") {
      return;
    }
    setFormError("");
    setFormMessage("");

    switch (view) {
      case "workers":
        createMutation.mutate({
          view,
          body: {
            name: createName,
            furigana: null,
            email: createEmail || null,
            phone: createPhone || null,
            sole_proprietor_name: null,
            emergency_contact_name_kana: null,
            emergency_contact_phone: null,
            gender: null,
            invoice_registration_status: null,
            invoice_number: null,
            introducer_supplier_id: createSupplierId || null,
            notes: createNotes || null,
            is_active: createIsActive,
            smoking_area_ok: null,
            has_p_shirt: null,
            has_best: null,
            stores_training_done: null,
            pioneer_training_done: null,
            p_shirt_count: null,
            license_type: null,
            tags: createTags,
          },
        });
        break;
      case "suppliers":
        createMutation.mutate({
          view,
          body: {
            name: createName,
            contact_email: createContactEmail || null,
            contact_phone: createContactPhone || null,
            supplier_type: null,
            entity_type: null,
            payout_terms_days: Number(createTermsDays || 70),
            default_daily_price: createDefaultDailyPrice || null,
            is_active: createIsActive,
            notes: createNotes || null,
          },
        });
        break;
      case "clients":
        if ((!createContactName.trim() && (createContactRole.trim() || createContactPhone.trim() || createContactEmail.trim())) || extraContacts.some((contact) => !contact.name.trim())) {
          setFormError("役職・電話・メールを入力した担当者、および追加した担当者の氏名を入力してください"); return;
        }
        if (createPostalCode && !/^[0-9]{7}$/.test(normalizePostalCode(createPostalCode))) {
          setFormError("郵便番号は7桁で入力してください"); return;
        }
        createMutation.mutate({ view, body: { postal_code: normalizePostalCode(createPostalCode) || null, notes: createNotes || null, name: createName, code: createCode || null, address: createAddress || null, phone: createPhone || null, contact_name: createContactName || null, contact_email: createContactEmail || null, billing_email: null,
          contacts: [...(createContactName.trim() ? [{ name: createContactName.trim(), role: createContactRole.trim() || null, phone: createContactPhone || null, email: createContactEmail || null }] : []), ...extraContacts.map((contact) => ({ name: contact.name.trim(), role: contact.role.trim() || null, phone: contact.phone || null, email: contact.email || null }))] } });
        break;
      case "sites":
        createMutation.mutate({ view, body: { name: createName, code: createCode || null, address: createAddress || null } });
        break;
      case "project_types":
        createMutation.mutate({ view, body: { name: createName, code: createCode || null, category_level: createProjectTypeLevel, parent_id: createProjectTypeLevel === "major" ? null : createProjectTypeParentId || null, description: createDescription || null } });
        break;
      case "roles":
        createMutation.mutate({ view, body: { name: createName, code: createCode || null, description: createDescription || null } });
        break;
      case "vanzai_staff":
        createMutation.mutate({
          view,
          body: {
            name: createName,
            role: createVanzaiStaffRole || null,
            linked_worker_id: createLinkedWorkerId || null,
            playing_manager_fee_type: createVanzaiStaffRole === "プレイングマネージャー" ? (createPlayingManagerFeeType as "subordinate_man_days" | "fixed_amount") : null,
            playing_manager_fixed_fee: createVanzaiStaffRole === "プレイングマネージャー" && createPlayingManagerFeeType === "fixed_amount" ? createPlayingManagerFixedFee || null : null,
            phone: createPhone || null,
            email: createEmail || null,
            is_active: createIsActive,
            notes: createNotes || null,
          },
        });
        break;
    }
  }

  function handleUpdate() {
    if (user?.role !== "admin") {
      return;
    }
    setEditError("");
    setEditMessage("");

    if (selectedWorker) {
      if (!editGuard) {
        setEditError("比較票がないため保存しませんでした。最新の内容を読み込んでから、もう一度保存してください。");
        setEditNeedsReload(true);
        return;
      }
      updateMutation.mutate({
        view: "workers",
        id: selectedWorker.id,
        body: {
          edit_guard: editGuard,
          name: editName,
          furigana: selectedWorker.furigana ?? null,
          email: editEmail || null,
          phone: editPhone || null,
          sole_proprietor_name: selectedWorker.sole_proprietor_name ?? null,
          emergency_contact_name_kana: selectedWorker.emergency_contact_name_kana ?? null,
          emergency_contact_phone: selectedWorker.emergency_contact_phone ?? null,
          gender: selectedWorker.gender ?? null,
          invoice_registration_status: selectedWorker.invoice_registration_status ?? null,
          invoice_number: selectedWorker.invoice_number ?? null,
          introducer_supplier_id: editSupplierId || null,
          notes: editNotes || null,
          is_active: editIsActive,
          smoking_area_ok: selectedWorker.smoking_area_ok ?? null,
          has_p_shirt: selectedWorker.has_p_shirt ?? null,
          has_best: selectedWorker.has_best ?? null,
          stores_training_done: selectedWorker.stores_training_done ?? null,
          pioneer_training_done: selectedWorker.pioneer_training_done ?? null,
          p_shirt_count: selectedWorker.p_shirt_count ?? null,
          license_type: selectedWorker.license_type ?? null,
          tags: editTags,
        },
      });
      return;
    }

    if (selectedSupplier) {
      updateMutation.mutate({
        view: "suppliers",
        id: selectedSupplier.id,
        body: {
          name: editName,
          contact_email: editEmail || null,
          contact_phone: editContactPhone || null,
          supplier_type: selectedSupplier.supplier_type ?? null,
          entity_type: selectedSupplier.entity_type ?? null,
          payout_terms_days: Number(editTermsDays || 70),
          default_daily_price: editDefaultDailyPrice || null,
          is_active: editIsActive,
          notes: editNotes || null,
        },
      });
    }

    if (selectedVanzaiStaff) {
      updateMutation.mutate({
        view: "vanzai_staff",
        id: selectedVanzaiStaff.id,
        body: {
          name: editName,
          role: editVanzaiStaffRole || null,
          linked_worker_id: editLinkedWorkerId || null,
          playing_manager_fee_type: editVanzaiStaffRole === "プレイングマネージャー" ? (editPlayingManagerFeeType as "subordinate_man_days" | "fixed_amount") : null,
          playing_manager_fixed_fee: editVanzaiStaffRole === "プレイングマネージャー" && editPlayingManagerFeeType === "fixed_amount" ? editPlayingManagerFixedFee || null : null,
          phone: editPhone || null,
          email: editEmail || null,
          is_active: editIsActive,
          notes: editNotes || null,
        },
      });
    }
  }

  if (activeQuery.isLoading) {
    return <LoadingOverlay label="マスタ一覧を読み込み中..." />;
  }

  if (activeQuery.error instanceof ApiError && activeQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (activeQuery.isError || !activeQuery.data) {
    return <ErrorState title="マスタ一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  const total = activeQuery.data.total;
  const showActiveFilter = view === "workers" || view === "suppliers" || view === "vanzai_staff";
  const canEditMaster = user?.role === "admin" && (selectedWorker || selectedSupplier || selectedVanzaiStaff);

  return (
    <div className="page-stack">
      <PageHeader title="マスタ一覧" description="稼働者・下請け・クライアント等のマスタデータを参照します。" />

      <section className="upload-card">
        <div className="master-view-switch" role="group" aria-label="表示切替">
          <strong>表示切替</strong>
          {(Object.keys(VIEW_LABELS) as MasterView[]).map((v) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => handleViewChange(v)} style={{ borderColor: VIEW_COLORS[v] }}>
              {VIEW_LABELS[v]}
            </button>
          ))}
        </div>
      </section>

      {user?.role === "admin" && <div className="master-list-actions"><button type="button" className="primary-button" onClick={() => { resetCreateForm(); clearEditor(); setCreateOpen(true); }}>新規追加</button></div>}
      {formMessage && <p role="status">{formMessage}</p>}
      {user?.role === "admin" && createOpen ? (
        <ProfileDialog title={`${VIEW_LABELS[view]}の新規追加`} onClose={() => { if (!createMutation.isPending) setCreateOpen(false); }}>
        <section className="card master-form" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <strong>{VIEW_LABELS[view]}を追加</strong>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              名称
              <input value={createName} onChange={(event) => setCreateName(event.target.value)} placeholder="名称" />
            </label>

            {(view === "clients" || view === "sites" || view === "project_types" || view === "roles") ? (
              <label>
                コード
                <input value={createCode} onChange={(event) => setCreateCode(event.target.value)} placeholder="任意" />
              </label>
            ) : null}

            {view === "workers" ? (
              <>
                <label>
                  メール
                  <input value={createEmail} onChange={(event) => setCreateEmail(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  電話
                  <input value={createPhone} onChange={(event) => setCreatePhone(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  紹介会社
                  <select value={createSupplierId} onChange={(event) => setCreateSupplierId(event.target.value)}>
                    <option value="">未設定</option>
                    {(supplierOptionsQuery.data?.items ?? []).map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}

            {view === "vanzai_staff" ? (
              <>
                <label>
                  役職
                  <select value={createVanzaiStaffRole} onChange={(event) => setCreateVanzaiStaffRole(event.target.value)}>
                    <option value="">未設定</option>
                    {VANZAI_STAFF_ROLE_OPTIONS.map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                </label>
                <label>
                  対応稼働者
                  <select value={createLinkedWorkerId} onChange={(event) => setCreateLinkedWorkerId(event.target.value)}>
                    <option value="">未設定</option>
                    {(workerOptionsQuery.data?.items ?? []).map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
                {createVanzaiStaffRole === "プレイングマネージャー" ? (
                  <>
                    <label>
                      PM計算方式
                      <select value={createPlayingManagerFeeType} onChange={(event) => setCreatePlayingManagerFeeType(event.target.value)}>
                        {PLAYING_MANAGER_FEE_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </label>
                    {createPlayingManagerFeeType === "fixed_amount" ? (
                      <label>
                        PM固定額
                        <input value={createPlayingManagerFixedFee} onChange={(event) => setCreatePlayingManagerFixedFee(event.target.value)} placeholder="100000" />
                      </label>
                    ) : null}
                  </>
                ) : null}
                <label>
                  メール
                  <input value={createEmail} onChange={(event) => setCreateEmail(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  電話
                  <input value={createPhone} onChange={(event) => setCreatePhone(event.target.value)} placeholder="任意" />
                </label>
              </>
            ) : null}

            {view === "suppliers" ? (
              <>
                <label>
                  メール
                  <input value={createContactEmail} onChange={(event) => setCreateContactEmail(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  電話
                  <input value={createContactPhone} onChange={(event) => setCreateContactPhone(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  支払サイト(日)
                  <input type="number" min="0" value={createTermsDays} onChange={(event) => setCreateTermsDays(event.target.value)} />
                </label>
                <label>
                  日額単価
                  <input value={createDefaultDailyPrice} onChange={(event) => setCreateDefaultDailyPrice(event.target.value)} placeholder="任意" />
                </label>
              </>
            ) : null}

            {view === "clients" ? (
              <>
                <label>
                  会社電話番号
                  <input type="tel" maxLength={20} value={createPhone} onChange={(event) => setCreatePhone(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  担当者1の氏名
                  <input value={createContactName} onChange={(event) => setCreateContactName(event.target.value)} placeholder="任意" />
                </label>
                <label>担当者1の役職<input maxLength={100} value={createContactRole} onChange={(event) => setCreateContactRole(event.target.value)} placeholder="任意" /></label>
                <label>
                  担当者1の電話番号
                  <input type="tel" maxLength={20} value={createContactPhone} onChange={(event) => setCreateContactPhone(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  担当者1のメール
                  <input value={createContactEmail} onChange={(event) => setCreateContactEmail(event.target.value)} placeholder="任意" />
                </label>
              </>
            ) : null}

            {view === "project_types" ? (
              <>
                <label>
                  階層
                  <select value={createProjectTypeLevel} onChange={(event) => setCreateProjectTypeLevel(event.target.value)}>
                    <option value="major">major</option>
                    <option value="middle">middle</option>
                    <option value="minor">minor</option>
                  </select>
                </label>
                <label>
                  親種別
                  <select value={createProjectTypeParentId} onChange={(event) => setCreateProjectTypeParentId(event.target.value)} disabled={createProjectTypeLevel === "major"}>
                    <option value="">未設定</option>
                    {projectTypeOptions.map((item) => (
                      <option key={item.id} value={item.id}>{item.label}</option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
          </div>

          {view === "clients" && <div className="master-client-contacts">
            {extraContacts.map((contact, index) => <fieldset key={contact.id}><legend>担当者 {index + 2}</legend><div className="master-form-grid">
              <label>氏名<input aria-label={`担当者${index + 2}の氏名`} maxLength={100} value={contact.name} onChange={(e) => setExtraContacts((rows) => rows.map((row) => row.id === contact.id ? { ...row, name: e.target.value } : row))} /></label>
              <label>役職<input aria-label={`担当者${index + 2}の役職`} maxLength={100} value={contact.role} onChange={(e) => setExtraContacts((rows) => rows.map((row) => row.id === contact.id ? { ...row, role: e.target.value } : row))} /></label>
              <label>電話番号<input type="tel" aria-label={`担当者${index + 2}の電話番号`} maxLength={20} value={contact.phone} onChange={(e) => setExtraContacts((rows) => rows.map((row) => row.id === contact.id ? { ...row, phone: e.target.value } : row))} /></label>
              <label>メール<input type="email" aria-label={`担当者${index + 2}のメール`} value={contact.email} onChange={(e) => setExtraContacts((rows) => rows.map((row) => row.id === contact.id ? { ...row, email: e.target.value } : row))} /></label>
            </div><button type="button" onClick={() => setExtraContacts((rows) => rows.filter((row) => row.id !== contact.id))}>未保存の担当者 {index + 2} を外す</button></fieldset>)}
            <button type="button" className="btn btn-ghost" onClick={() => setExtraContacts((rows) => [...rows, { id: crypto.randomUUID(), name: "", role: "", phone: "", email: "" }])}>担当者を追加</button>
          </div>}

          {view === "clients" && <>
            <label style={{ maxWidth: "220px" }}>郵便番号<input value={createPostalCode} onChange={(e) => setCreatePostalCode(e.target.value)} autoComplete="postal-code" inputMode="numeric" placeholder="例: 123-4567" /></label>
            {postalMessage && <p role="status" style={{ margin: 0 }}>{postalMessage}</p>}
            {postalChoices.map((address) => <button key={address} type="button" className="ghost-button" onClick={() => { setCreateAddress(address); lastAutoAddress.current = address; setPostalChoices([]); setPostalMessage("番地・建物名を確認・入力してください。"); }}>{address}</button>)}
          </>}
          {(view === "clients" || view === "sites") ? (
            <label>
              住所
              <textarea aria-label="住所" value={createAddress} onChange={(event) => setCreateAddress(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
            </label>
          ) : null}

          {view === "clients" && <label>社内メモ<textarea value={createNotes} onChange={(e) => setCreateNotes(e.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} /></label>}

          {view === "workers" ? (
            <WorkerTagPicker options={workerTagOptions} selected={createTags} onChange={setCreateTags} />
          ) : null}

          {(view === "workers" || view === "suppliers" || view === "vanzai_staff") ? (
            <>
              <label>
                メモ
                <textarea value={createNotes} onChange={(event) => setCreateNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input type="checkbox" checked={createIsActive} onChange={(event) => setCreateIsActive(event.target.checked)} />
                有効
              </label>
            </>
          ) : null}

          {(view === "project_types" || view === "roles") ? (
            <label>
              説明
              <textarea value={createDescription} onChange={(event) => setCreateDescription(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
            </label>
          ) : null}

          {formError ? <p className="form-error">{formError}</p> : null}
          {formMessage ? <p>{formMessage}</p> : null}
          <div>
            <button type="button" className="primary-button master-add-button" onClick={handleCreate} disabled={!createName.trim() || createMutation.isPending}>
              {createMutation.isPending ? "作成中..." : `${VIEW_LABELS[view]}を追加`}
            </button>
          </div>
        </section>
        </ProfileDialog>
      ) : null}

      {canEditMaster ? (
        <ProfileDialog title={selectedWorker ? "稼働者を編集" : selectedSupplier ? "下請けを編集" : "VANZAI担当者を編集"} onClose={() => { if (!updateMutation.isPending) clearEditor(); }}>
        <section className="card master-form" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
      <strong>{selectedWorker ? "稼働者を編集" : selectedSupplier ? "下請けを編集" : "VANZAI担当者を編集"}</strong>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              名称
              <input value={editName} onChange={(event) => setEditName(event.target.value)} />
            </label>
            <label>
              メール
              <input value={editEmail} onChange={(event) => setEditEmail(event.target.value)} />
            </label>
            {selectedWorker ? (
              <>
                <label>
                  電話
                  <input value={editPhone} onChange={(event) => setEditPhone(event.target.value)} />
                </label>
                <label>
                  紹介会社
                  <select value={editSupplierId} onChange={(event) => setEditSupplierId(event.target.value)}>
                    <option value="">未設定</option>
                    {(supplierOptionsQuery.data?.items ?? []).map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
            {selectedSupplier ? (
              <>
                <label>
                  電話
                  <input value={editContactPhone} onChange={(event) => setEditContactPhone(event.target.value)} />
                </label>
                <label>
                  支払サイト(日)
                  <input type="number" min="0" value={editTermsDays} onChange={(event) => setEditTermsDays(event.target.value)} />
                </label>
                <label>
                  日額単価
                  <input value={editDefaultDailyPrice} onChange={(event) => setEditDefaultDailyPrice(event.target.value)} />
                </label>
              </>
            ) : null}
            {selectedVanzaiStaff ? (
              <>
                <label>
                  役職
                  <select value={editVanzaiStaffRole} onChange={(event) => setEditVanzaiStaffRole(event.target.value)}>
                    <option value="">未設定</option>
                    {VANZAI_STAFF_ROLE_OPTIONS.map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                </label>
                <label>
                  対応稼働者
                  <select value={editLinkedWorkerId} onChange={(event) => setEditLinkedWorkerId(event.target.value)}>
                    <option value="">未設定</option>
                    {(workerOptionsQuery.data?.items ?? []).map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
                {editVanzaiStaffRole === "プレイングマネージャー" ? (
                  <>
                    <label>
                      PM計算方式
                      <select value={editPlayingManagerFeeType} onChange={(event) => setEditPlayingManagerFeeType(event.target.value)}>
                        {PLAYING_MANAGER_FEE_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </label>
                    {editPlayingManagerFeeType === "fixed_amount" ? (
                      <label>
                        PM固定額
                        <input value={editPlayingManagerFixedFee} onChange={(event) => setEditPlayingManagerFixedFee(event.target.value)} />
                      </label>
                    ) : null}
                  </>
                ) : null}
              </>
            ) : null}
          </div>
          {selectedWorker ? (
            <WorkerTagPicker options={workerTagOptions} selected={editTags} onChange={setEditTags} />
          ) : null}
          <label>
            メモ
            <textarea value={editNotes} onChange={(event) => setEditNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input type="checkbox" checked={editIsActive} onChange={(event) => setEditIsActive(event.target.checked)} />
            有効
          </label>
          {editError ? <p className="form-error">{editError}</p> : null}
          {editNeedsReload && selectedWorker ? (
            <button type="button" className="ghost-button" onClick={() => { void openWorkerEditor(selectedWorker); }}>
              最新の内容を読み込む
            </button>
          ) : null}
          {editMessage ? <p>{editMessage}</p> : null}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button type="button" className="primary-button" onClick={handleUpdate} disabled={!editName.trim() || updateMutation.isPending}>
              {updateMutation.isPending ? "更新中..." : "更新する"}
            </button>
            <button type="button" className="ghost-button" onClick={clearEditor}>編集を閉じる</button>
          </div>
          {selectedSupplier ? (
            <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: "0.75rem", marginTop: "0.25rem", display: "grid", gap: "0.75rem" }}>
              <strong style={{ fontSize: "0.9rem" }}>振込先口座</strong>
              {supplierBankAccountsQuery.isLoading ? <p style={{ margin: 0, color: "#6b7280", fontSize: "0.875rem" }}>読み込み中...</p> : null}
              {supplierBankAccountsQuery.data?.items && supplierBankAccountsQuery.data.items.length > 0 ? (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      <th style={{ padding: "0.25rem 0.5rem" }}>銀行</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>支店</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>種別</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>口座番号</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>口座名義(カナ)</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>有効開始</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>有効終了</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>主</th>
                      <th style={{ padding: "0.25rem 0.5rem" }}>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {supplierBankAccountsQuery.data.items.map((account: SupplierBankAccountItem) => (
                      <tr key={account.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{account.bank_name}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{account.branch_name}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{account.account_type}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{formatMaskedAccountNumber(account.account_number)}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{account.account_holder_kana}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{formatDate(account.effective_from)}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{formatDate(account.effective_until)}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>{account.is_primary ? "✓" : ""}</td>
                        <td style={{ padding: "0.25rem 0.5rem" }}>
                          <button type="button" style={{ fontSize: "0.8rem" }} onClick={() => openSupplierBankEditor(account)}>編集</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : supplierBankAccountsQuery.isLoading ? null : (
                <p style={{ margin: "0.25rem 0", color: "#9ca3af", fontSize: "0.875rem" }}>口座未登録</p>
              )}
              {selectedSupplierBankAccount ? (
                <section style={{ borderTop: "1px solid #e5e7eb", paddingTop: "0.75rem", display: "grid", gap: "0.5rem" }}>
                  <strong style={{ fontSize: "0.85rem" }}>口座を編集</strong>
                  <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
                    <label style={{ fontSize: "0.8rem" }}>
                      銀行名 *
                      <input value={supplierEditBankName} onChange={(event) => setSupplierEditBankName(event.target.value)} />
                    </label>
                    <label style={{ fontSize: "0.8rem" }}>
                      支店名 *
                      <input value={supplierEditBranchName} onChange={(event) => setSupplierEditBranchName(event.target.value)} />
                    </label>
                    <label style={{ fontSize: "0.8rem" }}>
                      支店コード
                      <input value={supplierEditBranchCode} onChange={(event) => setSupplierEditBranchCode(event.target.value)} maxLength={10} />
                    </label>
                    <label style={{ fontSize: "0.8rem" }}>
                      種別 *
                      <select value={supplierEditAccountType} onChange={(event) => setSupplierEditAccountType(event.target.value)}>
                        <option value="普通">普通</option>
                        <option value="当座">当座</option>
                        <option value="貯蓄">貯蓄</option>
                      </select>
                    </label>
                    <label style={{ fontSize: "0.8rem" }}>
                      口座番号 *
                      <input value={supplierEditAccountNumber} onChange={(event) => setSupplierEditAccountNumber(event.target.value)} maxLength={20} />
                    </label>
                    <label style={{ fontSize: "0.8rem" }}>
                      口座名義(カナ) *
                      <input value={supplierEditHolderKana} onChange={(event) => setSupplierEditHolderKana(event.target.value)} />
                    </label>
                    <label style={{ fontSize: "0.8rem" }}>
                      有効開始日 *
                      <input type="date" value={supplierEditEffectiveFrom} onChange={(event) => setSupplierEditEffectiveFrom(event.target.value)} />
                    </label>
                    <label style={{ fontSize: "0.8rem" }}>
                      有効終了日
                      <input type="date" value={supplierEditEffectiveUntil} onChange={(event) => setSupplierEditEffectiveUntil(event.target.value)} />
                    </label>
                    <label style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <input type="checkbox" checked={supplierEditIsPrimary} onChange={(event) => setSupplierEditIsPrimary(event.target.checked)} style={{ width: "auto" }} />
                      主口座
                    </label>
                  </div>
                  {supplierBankEditError ? <p className="form-error" style={{ fontSize: "0.8rem" }}>{supplierBankEditError}</p> : null}
                  {supplierBankEditMessage ? <p style={{ margin: 0, color: "#16a34a", fontSize: "0.8rem" }}>{supplierBankEditMessage}</p> : null}
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="primary-button"
                      onClick={() => updateSupplierBankAccountMutation.mutate()}
                      disabled={!supplierEditBankName.trim() || !supplierEditBranchName.trim() || !supplierEditAccountNumber.trim() || !supplierEditHolderKana.trim() || !supplierEditEffectiveFrom || updateSupplierBankAccountMutation.isPending}
                    >
                      {updateSupplierBankAccountMutation.isPending ? "更新中..." : "口座を更新"}
                    </button>
                    <button type="button" className="ghost-button" onClick={() => setSelectedSupplierBankAccount(null)}>
                      編集を閉じる
                    </button>
                  </div>
                </section>
              ) : null}
              <details>
                <summary style={{ cursor: "pointer", fontSize: "0.85rem", color: "#4b5563" }}>口座を追加</summary>
                <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", marginTop: "0.5rem" }}>
                  <label style={{ fontSize: "0.8rem" }}>
                    銀行名 *
                    <input value={supplierBankBankName} onChange={(event) => setSupplierBankBankName(event.target.value)} placeholder="例: ゆうちょ銀行" />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    支店名 *
                    <input value={supplierBankBranchName} onChange={(event) => setSupplierBankBranchName(event.target.value)} placeholder="例: 本店" />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    支店コード
                    <input value={supplierBankBranchCode} onChange={(event) => setSupplierBankBranchCode(event.target.value)} placeholder="任意" maxLength={10} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    種別 *
                    <select value={supplierBankAccountType} onChange={(event) => setSupplierBankAccountType(event.target.value)}>
                      <option value="普通">普通</option>
                      <option value="当座">当座</option>
                      <option value="貯蓄">貯蓄</option>
                    </select>
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    口座番号 *
                    <input value={supplierBankAccountNumber} onChange={(event) => setSupplierBankAccountNumber(event.target.value)} placeholder="例: 1234567" maxLength={20} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    口座名義(カナ) *
                    <input value={supplierBankHolderKana} onChange={(event) => setSupplierBankHolderKana(event.target.value)} placeholder="例: ヤマダ タロウ" />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    有効開始日 *
                    <input type="date" value={supplierBankEffectiveFrom} onChange={(event) => setSupplierBankEffectiveFrom(event.target.value)} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    有効終了日
                    <input type="date" value={supplierBankEffectiveUntil} onChange={(event) => setSupplierBankEffectiveUntil(event.target.value)} />
                  </label>
                  <label style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <input type="checkbox" checked={supplierBankIsPrimary} onChange={(event) => setSupplierBankIsPrimary(event.target.checked)} style={{ width: "auto" }} />
                    主口座
                  </label>
                </div>
                {supplierBankFormError ? <p className="form-error" style={{ fontSize: "0.8rem" }}>{supplierBankFormError}</p> : null}
                {supplierBankFormMessage ? <p style={{ margin: 0, color: "#16a34a", fontSize: "0.8rem" }}>{supplierBankFormMessage}</p> : null}
                <button
                  type="button"
                  className="primary-button"
                  style={{ marginTop: "0.5rem" }}
                  onClick={() => createSupplierBankAccountMutation.mutate({
                    bank_name: supplierBankBankName,
                    branch_name: supplierBankBranchName,
                    branch_code: supplierBankBranchCode || null,
                    account_type: supplierBankAccountType,
                    account_number: supplierBankAccountNumber,
                    account_holder_kana: supplierBankHolderKana,
                    transfer_destination_name: null,
                    effective_from: supplierBankEffectiveFrom,
                    effective_until: supplierBankEffectiveUntil || null,
                    is_primary: supplierBankIsPrimary,
                  })}
                  disabled={
                    !supplierBankBankName.trim() ||
                    !supplierBankBranchName.trim() ||
                    !supplierBankAccountNumber.trim() ||
                    !supplierBankHolderKana.trim() ||
                    !supplierBankEffectiveFrom ||
                    createSupplierBankAccountMutation.isPending
                  }
                >
                  {createSupplierBankAccountMutation.isPending ? "登録中..." : "口座を登録"}
                </button>
              </details>
            </div>
          ) : null}
        </section>
        </ProfileDialog>
      ) : null}

      <FilterBar>
        <label>
          検索
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder={`${VIEW_LABELS[view]}名で検索`} />
        </label>
        {showActiveFilter ? (
          <label>
            状態
            <select value={isActive} onChange={(e) => { setIsActive(e.target.value); setPage(0); }}>
              <option value="">すべて</option>
              <option value="true">有効のみ</option>
              <option value="false">無効のみ</option>
            </select>
          </label>
        ) : null}
      </FilterBar>

      {view === "workers" ? (
        <DataTable
          columns={[
            { key: "name", header: "氏名", render: (row) => row.name },
            { key: "email", header: "メール", render: (row) => row.email ?? "—" },
            { key: "phone", header: "電話", render: (row) => row.phone ?? "—" },
            { key: "supplier", header: "紹介会社", render: (row) => row.introducer_supplier_name ?? "—" },
            { key: "tags", header: "タグ", render: (row) => <WorkerTagList options={workerTagOptions} codes={row.tags} /> },
            { key: "status", header: "有効", render: (row) => <span className={`status-badge ${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "有効" : "無効"}</span> },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => openWorkerEditor(row)}>編集</button> : "—" },
          ]}
          rows={workersQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="稼働者はいません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "suppliers" ? (
        <DataTable
          columns={[
            { key: "name", header: "会社名", render: (row) => row.name },
            { key: "email", header: "メール", render: (row) => row.contact_email ?? "—" },
            { key: "phone", header: "電話", render: (row) => row.contact_phone ?? "—" },
            { key: "terms", header: "支払サイト(日)", render: (row) => String(row.payout_terms_days) },
            { key: "price", header: "日額単価", render: (row) => row.default_daily_price != null ? `¥${Number(row.default_daily_price).toLocaleString()}` : "—" },
            { key: "status", header: "有効", render: (row) => <span className={`status-badge ${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "有効" : "無効"}</span> },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => openSupplierEditor(row)}>編集</button> : "—" },
          ]}
          rows={suppliersQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="下請けはいません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "clients" ? (
        <>
          <DataTable
            columns={[
              { key: "name", header: "名称", render: (row) => row.name },
              { key: "code", header: "コード", render: (row) => row.code ?? "—" },
              { key: "contact_name", header: "担当者", render: (row) => row.contact_name ?? "—" },
              { key: "phone", header: "会社電話番号", render: (row) => row.phone ?? "—" },
              { key: "contact_email", header: "メール", render: (row) => row.contact_email ?? "—" },
              { key: "actions", header: "操作", render: (row) => <button type="button" onClick={() => setEditingClient(row)}>{user?.role === "admin" ? "編集" : "詳細"}</button> },
            ]}
            rows={clientsQuery.data?.items ?? []}
            getRowKey={(row) => row.id}
            emptyTitle="クライアントはいません"
            emptyDescription="CSV取り込みまたは直接登録で追加してください。"
          />
          {editingClient && <ClientCompanyEditor key={editingClient.id} client={editingClient} readOnly={user?.role !== "admin"} onClose={() => setEditingClient(null)} onSaved={async (updated) => {
            setEditingClient(updated);
            await Promise.all([
              queryClient.invalidateQueries({ queryKey: ["clients-page"] }),
              queryClient.invalidateQueries({ queryKey: ["clients-project-form"] }),
              queryClient.invalidateQueries({ queryKey: ["price-form-clients"] }),
              queryClient.invalidateQueries({ queryKey: ["order-source-clients"] }),
              queryClient.invalidateQueries({ queryKey: ["client-staff", updated.id] }),
              queryClient.invalidateQueries({ queryKey: ["order-source-contacts", updated.id] }),
            ]);
          }} />}

        </>
      ) : null}

      {view === "sites" ? (
        <DataTable
          columns={[
            { key: "name", header: "現場名", render: (row) => row.name },
            { key: "code", header: "コード", render: (row) => row.code ?? "—" },
            { key: "address", header: "住所", render: (row) => row.address ?? "—" },
          ]}
          rows={sitesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="現場はありません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "project_types" ? (
        <DataTable
          columns={[
            { key: "name", header: "種別名", render: (row) => row.name },
            { key: "code", header: "コード", render: (row) => row.code ?? "—" },
            { key: "category_level", header: "階層", render: (row) => row.category_level },
            { key: "description", header: "説明", render: (row) => row.description ?? "—" },
          ]}
          rows={projectTypesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="案件種別はありません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "roles" ? (
        <DataTable
          columns={[
            { key: "name", header: "役割名", render: (row) => row.name },
            { key: "code", header: "コード", render: (row) => row.code ?? "—" },
            { key: "description", header: "説明", render: (row) => row.description ?? "—" },
          ]}
          rows={rolesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="役割はありません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "vanzai_staff" ? (
        <DataTable
          columns={[
            { key: "name", header: "氏名", render: (row) => row.name },
            { key: "role", header: "役職", render: (row) => row.role ?? "—" },
            { key: "linked_worker", header: "対応稼働者", render: (row) => row.linked_worker_name ?? "—" },
            { key: "email", header: "メール", render: (row) => row.email ?? "—" },
            { key: "phone", header: "電話", render: (row) => row.phone ?? "—" },
            { key: "status", header: "有効", render: (row) => <span className={`status-badge ${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "有効" : "無効"}</span> },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => {
              setSelectedWorker(null);
              setSelectedSupplier(null);
              setSelectedVanzaiStaff(row);
              setEditName(row.name);
              setEditVanzaiStaffRole(row.role ?? "");
              setEditLinkedWorkerId(row.linked_worker_id ?? "");
              setEditPlayingManagerFeeType(row.playing_manager_fee_type ?? "subordinate_man_days");
              setEditPlayingManagerFixedFee(row.playing_manager_fixed_fee ?? "");
              setEditEmail(row.email ?? "");
              setEditPhone(row.phone ?? "");
              setEditNotes(row.notes ?? "");
              setEditIsActive(row.is_active);
              setEditError("");
              setEditMessage("");
            }}>編集</button> : "—" },
          ]}
          rows={vanzaiStaffQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="VANZAI担当者はいません"
          emptyDescription="担当者を追加してください。"
        />
      ) : null}

      <PaginationBar page={page} total={total} limit={PAGE_SIZE} onPrevious={() => setPage((p) => Math.max(0, p - 1))} onNext={() => setPage((p) => p + 1)} />
    </div>
  );
}
