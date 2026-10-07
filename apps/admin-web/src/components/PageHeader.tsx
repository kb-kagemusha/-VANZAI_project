import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  eyebrow = "参照専用",
  titleAction,
}: {
  title: string;
  description: string;
  eyebrow?: string;
  titleAction?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <div className="page-header-heading">
          <h2>{title}</h2>
          {titleAction}
        </div>
      </div>
      <p className="page-description">{description}</p>
    </div>
  );
}