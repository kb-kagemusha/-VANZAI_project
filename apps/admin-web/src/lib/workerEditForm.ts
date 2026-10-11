export type WorkerEditFields = {
  name: string;
  email: string;
  phone: string;
  supplierId: string;
  notes: string;
  isActive: boolean;
  tags: string[];
};

type GuardedWorker = {
  name: string;
  email: string | null;
  phone: string | null;
  introducer_supplier_id: string | null;
  notes: string | null;
  is_active: boolean;
  tags: string[];
};

/** 比較票と同時に返った稼働者から、次の保存に使う表示値を作る。 */
export function workerEditFieldsFromGuard(fresh: { edit_guard: string; worker: GuardedWorker }): WorkerEditFields {
  const current = fresh.worker;
  return {
    name: current.name,
    email: current.email ?? "",
    phone: current.phone ?? "",
    supplierId: current.introducer_supplier_id ?? "",
    notes: current.notes ?? "",
    isActive: current.is_active,
    tags: [...(current.tags ?? [])],
  };
}
