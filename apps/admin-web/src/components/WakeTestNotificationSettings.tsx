import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormDialog } from "./FormDialog";
import { getWakeTestNotificationSettings, saveWakeTestNotificationSettings, type WakeTestNotificationSettings as Settings } from "../lib/api/client";
import "../styles/wakeTestNotifications.css";

const key = ["wake-test-notification-settings"];
const localInput = (date: Date) => new Intl.DateTimeFormat("sv-SE", {timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false}).format(date).replace(" ", "T");
const display = (value: string) => new Date(value).toLocaleString("ja-JP", {timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"});

function SettingsDialog({ settings, onClose }: { settings: Settings; onClose: () => void }) {
  const client = useQueryClient();
  const [enabled, setEnabled] = useState(settings.enabled);
  const [until, setUntil] = useState(localInput(new Date(settings.enabled && settings.enabled_until ? settings.enabled_until : Date.now() + 60 * 60000)));
  const [revision, setRevision] = useState(settings.revision);
  const [error, setError] = useState("");
  const [reloading, setReloading] = useState(false);
  const save = useMutation({ mutationFn: saveWakeTestNotificationSettings,
    onSuccess: (result) => { client.setQueryData(key, result); onClose(); },
    onError: (cause) => setError(cause.message),
  });
  return <FormDialog open title="テスト案件のLINE通知（起床・人員確定）" size="compact" busy={save.isPending || reloading} onClose={onClose}>
    <form className="wake-test-settings-form" onSubmit={(event) => {
      event.preventDefault(); setError("");
      const expiry = enabled ? new Date(`${until}+09:00`) : null;
      if (expiry && Number.isNaN(expiry.getTime())) { setError("終了時刻を入力してください。"); return; }
      save.mutate({ enabled, enabled_until: expiry?.toISOString() ?? null, revision });
    }}>
      <p>全運営で共有する設定です。テスト予定の催促・未報告通知と、運営確定方式の募集・確定・終了通知を切り替えます。正式予定の通知と、画面の「テストも表示」は変わりません。</p>
      <fieldset className="order-draft-section" disabled={save.isPending || reloading}>
        <legend>テスト通知</legend>
        <div role="group" aria-label="テスト通知の送信" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className={`btn ${!enabled ? "btn-primary" : "btn-ghost"}`} aria-pressed={!enabled} onClick={() => setEnabled(false)}>送らない</button>
          <button type="button" className={`btn ${enabled ? "btn-primary" : "btn-ghost"}`} aria-pressed={enabled} onClick={() => setEnabled(true)}>送る（期限付き）</button>
        </div>
        {enabled && <label style={{ display: "grid", gap: 8, marginTop: 16 }}>終了時刻（日本時間）
          <input type="datetime-local" aria-label="終了時刻（日本時間）" required value={until} onChange={(event) => setUntil(event.target.value)} />
          <small>24時間以内を指定してください。期限で自動的に「送らない」に戻ります。</small>
        </label>}
      </fieldset>
      <p className="order-field-hint">有効化後に起床報告の期限が来るテスト予定が対象です。停止中の未報告通知はまとめて送信しません。同じ方に正式・テスト両方の予定がある日は正式予定を優先します。</p>
      {enabled && <p className="form-error">有効な間は実際にLINEを送信し、送信枠を使用します。未対応の場合は10分ごとに再通知されます。</p>}
      {error && <div role="alert"><p className="form-error">{error}</p><button type="button" className="btn btn-ghost" disabled={save.isPending || reloading} onClick={async () => {
        setReloading(true);
        try { const result = await getWakeTestNotificationSettings(); client.setQueryData(key, result); setRevision(result.revision); setEnabled(result.enabled); setUntil(localInput(new Date(result.enabled && result.enabled_until ? result.enabled_until : Date.now() + 60 * 60000))); setError(""); }
        catch (cause) { setError(cause instanceof Error ? cause.message : "設定を読み込めませんでした。"); }
        finally { setReloading(false); }
      }}>最新の設定を読み直す</button></div>}
      <div style={{ display: "flex", gap: 8 }}><button type="submit" className="btn btn-primary create-button" disabled={save.isPending || reloading}>{save.isPending ? "保存中…" : "設定を保存"}</button><button type="button" className="btn btn-ghost" disabled={save.isPending || reloading} onClick={onClose}>閉じる</button></div>
    </form>
  </FormDialog>;
}

export function WakeTestNotificationSettings() {
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: key, queryFn: getWakeTestNotificationSettings, refetchInterval: 15000 });
  const settings = query.data;
  const enabled = !!(settings?.enabled && settings.enabled_until && new Date(settings.enabled_until).getTime() > Date.now());
  return <section className="wake-test-notification-summary" aria-label="テスト通知の設定">
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
      <div><strong>テスト案件のLINE通知（起床・人員確定）</strong><p style={{ margin: "4px 0" }} role="status">{query.isError ? "設定を取得できませんでした" : !settings ? "設定を確認中…" : enabled ? `送る：${display(settings.enabled_until!)}まで（日本時間）` : "送らない"}</p>
      {settings?.updated_by && <small>最終変更：{settings.updated_by} {settings.updated_at && display(settings.updated_at)}</small>}</div>
      <button type="button" className="btn btn-ghost" disabled={!settings || query.isError} onClick={() => setOpen(true)}>テスト通知を設定</button>
      {query.isError && <button type="button" className="btn btn-ghost" onClick={() => query.refetch()}>再読み込み</button>}
    </div>
    {open && settings && <SettingsDialog settings={{...settings, enabled}} onClose={() => setOpen(false)} />}
  </section>;
}
