import { Link } from "react-router-dom";

/** 稼働予定は公式LINEで確認する（DEC-064）。旧URLを開いた人への案内。 */
export function LineScheduleNoticePage() {
  return (
    <section className="panel-card">
      <p className="panel-label">予定の確認</p>
      <h2>予定は公式LINEで確認してください</h2>
      <p>
        今日の予定・今後の予定・受託済みの発注依頼書は、公式LINEのメニュー（「スケジュール確認」「受託済みの発注依頼書」）から確認できます。
        起床報告も公式LINEのメニューから行います。
      </p>
      <p>公式LINEとの連携が済んでいない場合は、運営までお問い合わせください。</p>
      <Link to="/availability" className="text-link">事前予定へ</Link>
    </section>
  );
}
