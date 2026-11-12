import type { ReactNode } from "react";

/** Nothing to show yet, and what to do about it. */
export function EmptyState({ children }: Readonly<{ children: ReactNode }>) {
  return <p className="empty">{children}</p>;
}
