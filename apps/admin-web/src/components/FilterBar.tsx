import type { ReactNode } from "react";

export function FilterBar({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={className ? `filter-bar ${className}` : "filter-bar"}>{children}</div>;
}