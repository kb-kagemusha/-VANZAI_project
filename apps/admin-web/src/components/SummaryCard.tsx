export function SummaryCard({ label, value, accent }: { label: string; value: string | number; accent: string }) {
  return (
    <section className="summary-card" style={{ ["--accent" as string]: accent }}>
      <p>{label}</p>
      <strong>{value}</strong>
    </section>
  );
}