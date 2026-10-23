/** 氏名の正本には記号を混ぜず、開始日・タグの判定をAPIから受け取る。 */
export function WorkerName({ name, isNewcomer, isDirector }: { name: string; isNewcomer?: boolean; isDirector?: boolean }) {
  return <>{name}
    {isNewcomer ? <span role="img" aria-label="新人（稼働開始日から3か月）" title="新人（稼働開始日から3か月）" style={{ marginLeft: 2, whiteSpace: "nowrap" }}>🔰</span> : null}
    {isDirector ? <span role="img" aria-label="ディレクター可能" title="ディレクター可能" style={{ marginLeft: 3, display: "inline-flex", alignItems: "center", justifyContent: "center", width: 14, height: 14, borderRadius: 3, background: "#1d4ed8", color: "#fff", fontSize: 10, fontWeight: 800, lineHeight: 1, verticalAlign: "middle", whiteSpace: "nowrap" }}>D</span> : null}
  </>;
}
