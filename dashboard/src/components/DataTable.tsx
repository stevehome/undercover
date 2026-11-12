import type { ReactNode } from "react";

/** A table that lines up: numbers right-aligned, scrolling sideways on a narrow screen. */
export function DataTable({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="table-wrap">
      <table className="data">{children}</table>
    </div>
  );
}
