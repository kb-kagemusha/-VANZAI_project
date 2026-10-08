import { useState } from "react";

import { ApiError, changePassword } from "../lib/api/client";
import { formatRole } from "../lib/formatters";
import type { AuthUser } from "../types/api";
import { SEAL_COLORS } from "./previewSeal";

const SAMPLE_STATS = [
  { value: "12", label: "担当案件" },
  { value: "26", label: "処理した依頼" },
  { value: "8", label: "チーム" },
  { value: "3年", label: "在籍" },
];

export function PreviewProfile({
  user,
  displayedName,
  sealColor,
  onSealColor,
}: {
  user: AuthUser | null;
  displayedName: string;
  sealColor: string;
  onSealColor: (color: string) => void;
}) {
  const initial = displayedName.slice(0, 1) || "V";
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handlePassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(false);
    if (newPassword !== confirmPassword) {
      setError("新しいパスワードと確認用パスワードが一致しません。");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "パスワード変更に失敗しました。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="apex-preview__profile">
      <div className="apex-preview__heading-block">
        <h1 className="apex-preview__title">プロフィール</h1>
        <p className="apex-preview__lead">ログイン中のアカウントです。紹介と件数は見本です。</p>
      </div>
      <article className="apex-preview__card apex-preview__profile-hero">
        <div className="apex-preview__cover" />
        <span className="apex-preview__avatar is-large" style={{ background: sealColor }} aria-hidden="true">{initial}</span>
        <h2 className="apex-preview__profile-name">{displayedName || "名前未設定"}</h2>
        <p className="apex-preview__subtitle">{formatRole(user?.role)}</p>
        <dl className="apex-preview__profile-stats">
          {SAMPLE_STATS.map((stat) => (
            <div key={stat.label}>
              <dt>{stat.label}</dt>
              <dd>{stat.value}</dd>
            </div>
          ))}
        </dl>
        <p className="apex-preview__profile-bio">
          見本の紹介文です。案件の手配と請求までの流れを、誰でも同じ手順で回せるようにしています。実データの接続はまだありません。
        </p>
        <dl className="apex-preview__profile-facts">
          <div>
            <dt>メール</dt>
            <dd>{user?.email || "未設定"}</dd>
          </div>
          <div>
            <dt>所属</dt>
            <dd>運用（見本）</dd>
          </div>
          <div>
            <dt>拠点</dt>
            <dd>東京（見本）</dd>
          </div>
          <div>
            <dt>ユーザー名</dt>
            <dd>{user?.username || "未設定"}</dd>
          </div>
        </dl>
      </article>
      <article className="apex-preview__card">
        <h2 className="apex-preview__section-title">シールの色</h2>
        <p className="apex-preview__subtitle">丸いシール、選択中のメニュー、「新しい版を反映」、ダークモードの切り替えに反映します。</p>
        <div className="apex-preview__seal-choices" role="radiogroup" aria-label="シールの色">
          {SEAL_COLORS.map((color) => (
            <button
              key={color}
              type="button"
              role="radio"
              aria-checked={sealColor === color}
              aria-label={color}
              className={sealColor === color ? "apex-preview__seal-choice is-active" : "apex-preview__seal-choice"}
              style={{ background: color }}
              onClick={() => onSealColor(color)}
            />
          ))}
        </div>
      </article>
      <article className="apex-preview__card">
        <h2 className="apex-preview__section-title">パスワード変更</h2>
        <p className="apex-preview__subtitle">ログイン中のアカウントのパスワードを変更します。</p>
        {success ? <p className="apex-preview__status">パスワードを変更しました。</p> : null}
        {error ? <p className="apex-preview__status is-error" role="alert">{error}</p> : null}
        <form className="apex-preview__password" onSubmit={handlePassword}>
          <label className="apex-preview__field">
            現在のパスワード
            <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required autoComplete="current-password" />
          </label>
          <label className="apex-preview__field">
            新しいパスワード
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required autoComplete="new-password" />
          </label>
          <label className="apex-preview__field">
            新しいパスワード（確認）
            <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required autoComplete="new-password" />
          </label>
          <button type="submit" className="apex-preview__billing is-active" disabled={submitting}>
            {submitting ? "変更しています" : "パスワードを変更"}
          </button>
        </form>
      </article>
    </div>
  );
}
