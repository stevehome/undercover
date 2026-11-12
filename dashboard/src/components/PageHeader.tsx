import type { ReactNode } from "react";

/** The top of a page: what it is, and what it is for. */
export function PageHeader({
  title,
  children,
}: Readonly<{ title: ReactNode; children?: ReactNode }>) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      {children && <p className="page-purpose">{children}</p>}
    </header>
  );
}
