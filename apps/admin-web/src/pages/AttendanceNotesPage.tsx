import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "../components/PageHeader";
import { DataTable } from "../components/DataTable";
import { FormDialog } from "../components/FormDialog";
import { useAuth } from "../lib/auth/auth-context";
import { hasPermission } from "../lib/auth/permissions";
import { currentMonthInput, formatDateTime, toPeriodKey } from "../lib/formatters";
import { getAttendanceEvents, getAttendanceNotes, getAttendanceSchedules, recordAttendanceNote, voidAttendanceNote, type AttendanceNote, type AttendanceNoteBody } from "../lib/attendanceNotesApi";
import "./attendanceNotes.css";

export function AttendanceNotesPage() {
  const { user } = useAuth();
  const canWrite = hasPermission(user, "attendance_note_write");
  const cache = useQueryClient();
  const [month, setMonth] = useState(currentMonthInput());
  const [isTest, setTest] = useState(false);
  const [history, setHistory] = useState(false);
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(false);
  const [seriesId, setSeriesId] = useState("");
  const [day, setDay] = useState("");
  const [entryId, setEntryId] = useState("");
  const [kind, setKind] = useState<"late" | "cancel">("late");
  const [cause, setCause] = useState<AttendanceNoteBody["cause"]>("personal");
  const [minutes, setMinutes] = useState("");
  const [reason, setReason] = useState("");
  const [reporter, setReporter] = useState("");
  const [voidTarget, setVoidTarget] = useState<AttendanceNote | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const periodKey = toPeriodKey(month);
  const notes = useQuery({ queryKey: ["attendance-notes", periodKey, isTest, history, offset], enabled: !!periodKey,
    queryFn: () => getAttendanceNotes({ period_key: periodKey, is_test: isTest, include_voided: history, offset }) });
  const events = useQuery({ queryKey: ["attendance-events", periodKey, isTest], enabled: open && !!periodKey,
    queryFn: () => getAttendanceEvents(periodKey, isTest) });
  const schedules = useQuery({ queryKey: ["attendance-schedules", seriesId, day, isTest], enabled: open && !!seriesId && !!day,
    queryFn: () => getAttendanceSchedules(seriesId, day, isTest) });
  const invalidate = async () => {
    await cache.invalidateQueries({ queryKey: ["attendance-notes"] });
    await cache.invalidateQueries({ queryKey: ["attendance-payment-summary"] });
  };
  const save = useMutation({ mutationFn: () => recordAttendanceNote({ schedule_entry_id: entryId, kind, cause,
    late_minutes: kind === "late" ? Number(minutes) : null, reason, reported_by: reporter }),
    onSuccess: async () => { await invalidate(); setOpen(false); } });
  const remove = useMutation({ mutationFn: () => voidAttendanceNote(voidTarget!.id, voidReason),
    onSuccess: async () => { await invalidate(); setVoidTarget(null); } });
  const reset = () => { setSeriesId(""); setDay(""); setEntryId(""); setKind("late"); setCause("personal"); setMinutes(""); setReason(""); setReporter(""); save.reset(); setOpen(true); };
  return <div className="page-stack attendance-notes">
    <PageHeader eyebrow="運用" title="遅刻・キャンセル記録" description="現場責任者から受けた報告を記録し、月次の支払確認に表示します。" />
    {canWrite && <div className="record-list-actions"><button type="button" className="primary-button create-button" onClick={reset}>記録を登録</button></div>}
    <section className="card attendance-filters">
      <label>対象月<input type="month" value={month} onChange={e => { if (e.target.value) { setMonth(e.target.value); setOffset(0); } }} /></label>
      <div role="group" aria-label="記録の区分"><button type="button" className="secondary-button" aria-pressed={!isTest} onClick={() => { setTest(false); setOffset(0); }}>正式</button><button type="button" className="secondary-button" aria-pressed={isTest} onClick={() => { setTest(true); setOffset(0); }}>テスト</button></div>
      <label><input type="checkbox" checked={history} onChange={e => { setHistory(e.target.checked); setOffset(0); }} />取消済みも表示</label>
    </section>
    {notes.isPending && <p role="status">記録を読み込み中...</p>}
    {notes.isError && <p role="alert">記録を取得できません。再読み込みしてください。</p>}
    {notes.data && <><DataTable rows={notes.data.items} getRowKey={n => n.id} emptyTitle="記録はありません" emptyDescription="報告を受けた内容を「記録を登録」から登録してください。" columns={[
      { key: "date", header: "稼働日", render: n => n.work_date },
      { key: "event", header: "イベント", render: n => <>{n.project_name}{n.is_test && <small>（テスト）</small>}</> },
      { key: "worker", header: "稼働者", render: n => n.worker_name },
      { key: "summary", header: "内容・支払時の注意", render: n => <><strong>{n.summary}</strong><div>{n.payment_note}</div>{n.voided_at && <strong>取消済み：{n.void_reason}</strong>}</> },
      { key: "reason", header: "理由", render: n => <span style={{ whiteSpace: "pre-wrap" }}>{n.reason}</span> },
      { key: "reporter", header: "報告者／記録者", render: n => <>{n.reported_by}<div>{n.actor_name}／{formatDateTime(n.created_at)}</div></> },
      { key: "actions", header: "操作", render: n => canWrite && !n.voided_at ? <button type="button" className="attendance-void-button" onClick={() => { setVoidTarget(n); setVoidReason(""); remove.reset(); }}>記録を取り消す</button> : "—" },
    ]} /><div className="attendance-filters"><button type="button" className="secondary-button" disabled={offset === 0} onClick={() => setOffset(offset - 50)}>前へ</button><span>{notes.data.total}件</span><button type="button" className="secondary-button" disabled={offset + 50 >= notes.data.total} onClick={() => setOffset(offset + 50)}>次へ</button></div></>}
    <FormDialog open={open} title="遅刻・キャンセルを記録" busy={save.isPending} onClose={() => setOpen(false)}>
      <form className="attendance-form" onSubmit={e => { e.preventDefault(); save.mutate(); }}>
        <fieldset disabled={save.isPending}><legend>対象の稼働予定（{isTest ? "テスト" : "正式"}・{month}）</legend><div className="attendance-form-grid">
          <label>イベント<select required value={seriesId} onChange={e => { setSeriesId(e.target.value); setEntryId(""); }}><option value="">イベントを選択</option>{events.data?.items.map(event => <option key={event.series_id} value={event.series_id}>{event.project_name}（{event.series_id.slice(-6)}）</option>)}</select></label>
          <label>稼働日<input type="date" required value={day} min={`${month}-01`} max={`${month}-${new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate()}`} onChange={e => { setDay(e.target.value); setEntryId(""); }} /></label>
          <label>稼働予定者<select required disabled={!seriesId || !day || schedules.isFetching || schedules.isError} value={entryId} onChange={e => setEntryId(e.target.value)}><option value="">稼働予定者を選択</option>{schedules.data?.items.map(entry => <option key={entry.id} value={entry.id}>{entry.worker_name}／{entry.start_time?.slice(0, 5) ?? "時刻未設定"}{["cancelled", "superseded"].includes(entry.status) ? "（過去の予定）" : ""}</option>)}</select></label>
        </div>{events.isFetching || schedules.isFetching ? <p role="status">稼働予定を読み込み中...</p> : null}
        {events.isError || schedules.isError ? <p role="alert">稼働予定を取得できません。開き直してください。</p> : null}
        {seriesId && day && schedules.data?.items.length === 0 && <p>この日に受諾済みの稼働予定はありません。稼働日を確認してください。</p>}
        </fieldset>
        <fieldset disabled={save.isPending}><legend>報告内容</legend>
          <div role="group" aria-label="報告の種類" className="attendance-filters"><button type="button" className="secondary-button" aria-pressed={kind === "late"} onClick={() => setKind("late")}>遅刻</button><button type="button" className="secondary-button" aria-pressed={kind === "cancel"} onClick={() => setKind("cancel")}>キャンセル・中止</button></div>
          <div className="attendance-form-grid"><label>理由の区分<select value={cause} onChange={e => setCause(e.target.value as AttendanceNoteBody["cause"])}><option value="personal">本人都合（病気・怪我など）</option><option value="weather">台風・天候による中止</option><option value="other">その他・確認が必要</option></select></label>
          {kind === "late" && <label>遅刻時間（分）<input type="number" required min="1" max="10080" step="1" placeholder="例：2時間なら120" value={minutes} onChange={e => setMinutes(e.target.value)} /></label>}
          <label>報告者（現場責任者など）<input required maxLength={200} value={reporter} onChange={e => setReporter(e.target.value)} /></label></div>
          <label>理由・報告内容<textarea required maxLength={1000} rows={3} value={reason} onChange={e => setReason(e.target.value)} /></label>
          <p>{kind === "late" ? "遅刻時の支払額は自動計算せず、支払確認で判断します。" : cause === "personal" ? "本人都合のキャンセルは当日の支払対象外です。支払額の自動変更は行いません。" : cause === "weather" ? "受諾済みの日給・早出設営の固定報酬は満額保証です。" : "中止理由と支払の扱いを支払確認で判断してください。"}</p>
        </fieldset>
        {save.isError && <p role="alert">{save.error.message}</p>}
        <button type="submit" className="primary-button create-button" disabled={save.isPending || !entryId || !reason.trim() || !reporter.trim() || (kind === "late" && !minutes)}>記録を登録する</button>
      </form>
    </FormDialog>
    <FormDialog open={!!voidTarget} title="記録の取り消し" size="compact" busy={remove.isPending} onClose={() => setVoidTarget(null)}>
      <p>{voidTarget?.work_date}／{voidTarget?.project_name}／{voidTarget?.worker_name}：{voidTarget?.summary}</p>
      <p>元の記録は履歴に残します。訂正する場合は、取り消した後に正しい内容で登録してください。</p>
      <label>取消理由<textarea maxLength={1000} value={voidReason} onChange={e => setVoidReason(e.target.value)} /></label>
      {remove.isError && <p role="alert">{remove.error.message}</p>}
      <button type="button" className="attendance-void-button" disabled={!voidReason.trim() || remove.isPending} onClick={() => remove.mutate()}>取り消しを確定する</button>
    </FormDialog>
  </div>;
}
