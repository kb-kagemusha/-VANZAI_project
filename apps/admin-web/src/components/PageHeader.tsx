export function PageHeader({
  title,
  description,
  eyebrow = "参照専用",
}: {
  title: string;
  description: string;
  eyebrow?: string;
}) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      <p className="page-description">{description}</p>
    </div>
  );
}