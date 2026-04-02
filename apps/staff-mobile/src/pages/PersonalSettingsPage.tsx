import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, getWorkerAvailabilityPreferences, upsertWorkerAvailabilityPreferences } from "../lib/api/client";
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
} from "../lib/settings/staffPreferences";

export function PersonalSettingsPage() {
  const queryClient = useQueryClient();
  const [preferences, setPreferences] = useState<StaffAvailabilityPreferences>(getDefaultStaffAvailabilityPreferences);
  const [message, setMessage] = useState("");

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

  function applyPreset(nextPreferences: StaffAvailabilityPreferences) {
    setMessage("");
    setPreferences(nextPreferences);
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

      <section className="panel-card accent-blue settings-stack">
        <p className="panel-label">プリセット</p>
        <div className="settings-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              applyPreset({
                weeklyDefaultStatuses: { "0": "unavailable", "6": "unavailable" },
                holidayDefaultStatus: "unavailable",
                autoApplyEnabled: true,
              })
            }
          >
            土日祝休み
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              applyPreset({
                weeklyDefaultStatuses: { "0": "unavailable", "6": "unavailable" },
                holidayDefaultStatus: "",
                autoApplyEnabled: true,
              })
            }
          >
            土日休み
          </button>
          <button type="button" className="secondary-button" onClick={() => applyPreset(getDefaultStaffAvailabilityPreferences())}>
            設定なし
          </button>
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
    </div>
  );
}