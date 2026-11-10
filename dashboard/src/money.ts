/** Amounts are whole cents inside the dashboard, and two-decimal strings on the wire. */

/** Read a wire amount such as "1234.50" as whole cents. */
export function parseCents(amount: string): number {
  const [dollars = "0", cents = ""] = amount.split(".");
  return Number(dollars) * 100 + Number(cents.padEnd(2, "0"));
}

/** Write whole cents as a wire amount, such as 123450 as "1234.50". */
export function toWireAmount(cents: number): string {
  const rest = String(cents % 100).padStart(2, "0");
  return `${String(Math.trunc(cents / 100))}.${rest}`;
}

/** Format whole cents for people, such as 123450 as "$1,234.50". */
export function formatMoney(cents: number): string {
  const dollars = Math.trunc(cents / 100).toLocaleString("en-US");
  return `$${dollars}.${String(cents % 100).padStart(2, "0")}`;
}

/** Read a wire model cost such as "0.000138675" as whole billionths of a dollar. */
export function parseNanos(cost: string): number {
  const [dollars = "0", fraction = ""] = cost.split(".");
  return Number(dollars) * 1e9 + Number(fraction.padEnd(9, "0"));
}

/** Format a model cost in billionths of a dollar, such as "$0.0031". */
export function formatCost(nanos: number): string {
  const tenThousandths = Math.round(nanos / 1e5);
  const dollars = Math.trunc(tenThousandths / 1e4);
  return `$${String(dollars)}.${String(tenThousandths % 1e4).padStart(4, "0")}`;
}
