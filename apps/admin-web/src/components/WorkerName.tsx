/** 氏名の正本には記号を混ぜず、開始日から3か月の判定をAPIから受け取る。 */
export function WorkerName({ name, isNewcomer }: { name: string; isNewcomer?: boolean }) {
  return <>{name}{isNewcomer ? <span role="img" aria-label="新人（稼働開始日から3か月）" title="新人（稼働開始日から3か月）" style={{ marginLeft: 2, whiteSpace: "nowrap" }}>🔰</span> : null}</>;
}
