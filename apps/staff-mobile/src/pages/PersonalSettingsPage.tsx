import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, getWorkerAvailabilityPreferences, upsertWorkerAvailabilityPreferences, changePassword } from "../lib/api/client";
import { addDays, currentDateInput, formatDate, formatStatus } from "../lib/formatters";
import {
  availabilityStatusOptions,
  getAvailabilityTemplateDetail,
  getAvailabilityTemplateStatus,
  getDefaultStaffAvailabilityPreferences,
  normalizeStaffAvailabilityPreferences,
  toWorkerAvailabilityPreferencePayload,
  weekdayPreferenceOptions,
  type AvailabilityStatusValue,
  type StaffAvailabilityPreferences,
  type WeekdayPreferenceKey,
} from "../lib/settings/staffPreferences";
import { usePushNotification } from "../lib/hooks/usePushNotification";
import { useAppVersion } from "../lib/hooks/useAppVersion";

export function PersonalSettingsPage() {
  const queryClient = useQueryClient();
  const [preferences, setPreferences] = useState<StaffAvailabilityPreferences>(getDefaultStaffAvailabilityPreferences);
  const [message, setMessage] = useState("");
  const { permission, requestPermission } = usePushNotification();
  const { currentVersion, hasUpdate, refreshNow } = useAppVersion();
  const [pushMessage, setPushMessage] = useState<string | null>(null);

  // パスワード変更
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwSubmitting, setPwSubmitting] = useState(false);

  async function handlePasswordChange(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPwError(null);
    setPwSuccess(false);
    if (newPw !== confirmPw) {
      setPwError("新しいパスワードと確認用パスワードが一致しません");
      return;
    }
    setPwSubmitting(true);
    try {
      await changePassword(currentPw, newPw);
      setPwSuccess(true);
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : "パスワード変更に失敗しました");
    } finally {
      setPwSubmitting(false);
    }
  }

  const preferencesQuery = useQuery({
    queryKey: ["staff-availability-preferences"],
    queryFn: () => getWorkerAvailabilityPreferences(),
  });

  useEffect(() => {
    if (preferencesQuery.data) {
      setPreferences(normalizeStaffAvailabilityPreferences(preferencesQuery.data));
    }
  }, [preferencesQuery.data]);

  const previewDates = useMemo(() => {
    const start = currentDateInput();
    return Array.from({ length: 10 }, (_, index) => addDays(start, index));
  }, []);

  const saveMutation = useMutation({
    mutationFn: () => upsertWorkerAvailabilityPreferences(toWorkerAvailabilityPreferencePayload(preferences)),
    onSuccess: async (savedPreferences) => {
      queryClient.setQueryData(["staff-availability-preferences"], savedPreferences);
      await queryClient.invalidateQueries({ queryKey: ["staff-availability"] });
      setPreferences(normalizeStaffAvailabilityPreferences(savedPreferences));
      setMessage("個人設定を保存しました。事前予定には自動候補として表示されます。");
    },
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : "個人設定の保存に失敗しました。");
    },
  });

  const PRESETS: Array<{
    label: string;
    value: StaffAvailabilityPreferences;
  }> = [
    {
      label: "土日祝休み",
      value: { weeklyDefaultStatuses: { "0": "unavailable", "6": "unavailable" }, holidayDefaultStatus: "unavailable", autoApplyEnabled: true },
    },
    {
      label: "土日休み",
      value: { weeklyDefaultStatuses: { "0": "unavailable", "6": "unavailable" }, holidayDefaultStatus: "", autoApplyEnabled: true },
    },
    {
      label: "日曜休み",
      value: { weeklyDefaultStatuses: { "0": "unavailable" }, holidayDefaultStatus: "", autoApplyEnabled: true },
    },
    {
      label: "祝日休み",
      value: { weeklyDefaultStatuses: {}, holidayDefaultStatus: "unavailable", autoApplyEnabled: true },
    },
    {
      label: "設定なし",
      value: getDefaultStaffAvailabilityPreferences(),
    },
  ];

  function isPresetActive(preset: StaffAvailabilityPreferences): boolean {
    const weekdayKeys: WeekdayPreferenceKey[] = ["0", "1", "2", "3", "4", "5", "6"];
    for (const key of weekdayKeys) {
      const a = preferences.weeklyDefaultStatuses[key] ?? "";
      const b = preset.weeklyDefaultStatuses[key] ?? "";
      if (a !== b) return false;
    }
    return preferences.holidayDefaultStatus === preset.holidayDefaultStatus;
  }

  function handleSave() {
    saveMutation.mutate();
  }

  if (preferencesQuery.isLoading) {
    return <div className="panel-card">個人設定を読み込み中...</div>;
  }

  if (preferencesQuery.isError) {
    return (
      <div className="panel-card">
        <h2>個人設定を取得できませんでした</h2>
        <p>{preferencesQuery.error instanceof ApiError ? preferencesQuery.error.message : "API 疎通を確認してください。"}</p>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <section className="hero-panel sunrise">
        <p className="panel-label">個人設定</p>
        <h2>基本スケジュール</h2>
        <p>毎月の事前予定入力を楽にするため、曜日ごとの基本パターンを設定します。カレンダーでは保存前の状態を 自動候補 として区別して表示します。</p>
      </section>

      {/* プッシュ通知セクション */}
      <section className="push-settings-card">
        <div className="push-settings-icon">🔔</div>
        <div className="push-settings-body">
          <p className="push-settings-title">プッシュ通知</p>
          {!('Notification' in window) || !('PushManager' in window) ? (
            <p className="push-settings-sub">このブラウザはプッシュ通知に対応していません。</p>
          ) : permission === 'granted' ? (
            <p className="push-settings-sub push-settings-enabled">✓ 通知は有効です。シフト確定・お知らせをリアルタイムで受け取れます。</p>
          ) : permission === 'denied' ? (
            <p className="push-settings-sub">ブラウザに拒否されています。ブラウザの「サイトの設定」から通知を許可に変更してください。</p>
          ) : (
            <>
              <p className="push-settings-sub">シフト確定・変更・お知らせをリアルタイムで受け取れます。</p>
              <button
                type="button"
                className="push-settings-button"
                onClick={async () => {
                  const result = await requestPermission();
                  if (result === 'denied') {
                    setPushMessage('通知が拒否されました。ブラウザの設定から変更してください。');
                  } else if (result === 'granted') {
                    setPushMessage('通知を有効にしました！');
                  }
                }}
              >
                通知をONにする
              </button>
            </>
          )}
          {pushMessage ? <p className="push-settings-feedback">{pushMessage}</p> : null}
        </div>
      </section>

      <section className="panel-card accent-blue settings-stack">
        <p className="panel-label">プリセット</p>
        <div className="settings-preset-grid">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className={`preset-button${isPresetActive(preset.value) ? " preset-button--active" : ""}`}
              onClick={() => {
                setMessage("");
                setPreferences(preset.value);
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </section>

      <section className="panel-card settings-stack">
        <p className="panel-label">適用ルール</p>
        <label className="settings-checkbox settings-toggle-card">
          <input
            type="checkbox"
            checked={preferences.autoApplyEnabled}
            onChange={(event) => {
              setMessage("");
              setPreferences((current) => ({
                ...current,
                autoApplyEnabled: event.target.checked,
              }));
            }}
          />
          <span>基本スケジュールを事前予定に自動候補として表示する</span>
        </label>
        <p className="settings-helper-copy">オフにすると設定内容は保持したまま、月間カレンダーには自動候補を出しません。</p>

        <div className="weekday-settings-grid">
          {weekdayPreferenceOptions.map((option) => (
            <label key={option.value} className="weekday-setting-card">
              <span className="weekday-setting-name">{option.label}</span>
              <select
                value={preferences.weeklyDefaultStatuses[option.value] ?? ""}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setMessage("");
                  setPreferences((current) => {
                    const nextStatuses = { ...current.weeklyDefaultStatuses };
                    if (nextValue) {
                      nextStatuses[option.value] = nextValue as AvailabilityStatusValue;
                    } else {
                      delete nextStatuses[option.value];
                    }
                    return {
                      ...current,
                      weeklyDefaultStatuses: nextStatuses,
                    };
                  });
                }}
              >
                <option value="">自動設定なし</option>
                {availabilityStatusOptions.map((statusOption) => (
                  <option key={statusOption.value} value={statusOption.value}>
                    {statusOption.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>

        <label>
          祝日の自動候補
          <select
            value={preferences.holidayDefaultStatus}
            onChange={(event) => {
              setMessage("");
              setPreferences((current) => ({
                ...current,
                holidayDefaultStatus: event.target.value as StaffAvailabilityPreferences["holidayDefaultStatus"],
              }));
            }}
          >
            <option value="">自動設定なし</option>
            {availabilityStatusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="panel-card accent-sand settings-stack">
        <p className="panel-label">プレビュー</p>
        <div className="settings-preview-list">
          {previewDates.map((dateValue) => {
            const templateStatus = getAvailabilityTemplateStatus(dateValue, preferences);
            const templateDetail = getAvailabilityTemplateDetail(dateValue, preferences);

            return (
              <div key={dateValue} className="settings-preview-item">
                <div className="settings-preview-body">
                  <strong>{formatDate(dateValue)}</strong>
                  <span className="settings-preview-meta">{templateDetail.reason || (preferences.autoApplyEnabled ? "自動設定なし" : "自動候補オフ")}</span>
                </div>
                <span className={`status-pill ${templateStatus ? `status-${templateStatus}` : "status-pending"}`}>
                  {templateStatus ? formatStatus(templateStatus) : preferences.autoApplyEnabled ? "自動設定なし" : "候補オフ"}
                </span>
              </div>
            );
          })}
        </div>
        <p>
          事前予定の画面へ戻る: <Link to="/availability" className="text-link">事前予定を開く</Link>
        </p>
      </section>

      {message ? <section className="panel-card action-banner">{message}</section> : null}

      <div className="button-row">
        <button type="button" className="primary-button" onClick={handleSave} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "保存中..." : "設定を保存する"}
        </button>
      </div>

      <section className="panel-card settings-stack">
        <p className="panel-label">パスワード変更</p>
        {pwSuccess ? (
          <p style={{ color: "var(--success, #16a34a)", fontWeight: 600 }}>✓ パスワードを変更しました</p>
        ) : (
          <form onSubmit={handlePasswordChange} style={{ display: "grid", gap: "0.75rem" }}>
            <label>
              現在のパスワード
              <div className="password-input-wrapper">
                <input
                  type={showCurrentPw ? "text" : "password"}
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button type="button" className="password-toggle" onClick={() => setShowCurrentPw((v) => !v)} aria-label={showCurrentPw ? "隠す" : "表示する"}>
                  {showCurrentPw ? "隠す" : "表示"}
                </button>
              </div>
            </label>
            <label>
              新しいパスワード（8文字以上）
              <div className="password-input-wrapper">
                <input
                  type={showNewPw ? "text" : "password"}
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
                <button type="button" className="password-toggle" onClick={() => setShowNewPw((v) => !v)} aria-label={showNewPw ? "隠す" : "表示する"}>
                  {showNewPw ? "隠す" : "表示"}
                </button>
              </div>
            </label>
            <label>
              新しいパスワード（確認）
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
                autoComplete="new-password"
              />
            </label>
            {pwError ? <p className="form-error">{pwError}</p> : null}
            <button type="submit" className="primary-button" disabled={pwSubmitting}>
              {pwSubmitting ? "変更中..." : "パスワードを変更"}
            </button>
          </form>
        )}
      </section>

      {/* アプリバージョン */}
      <section className="app-version-section">
        <span className="app-version-label">バージョン: {currentVersion.split("-").pop()}</span>
        {hasUpdate ? (
          <button type="button" className="app-version-update-btn" onClick={refreshNow}>
            🔄 新しいバージョンに更新
          </button>
        ) : (
          <span className="app-version-latest">最新です</span>
        )}
      </section>
    </div>
  );
}