import { formatShare } from "../measures";
import { formatMoney } from "../money";
import type { AppealFigures as Figures } from "../types";

/** The Appeals page's figures: where the appeals stand, and the redress. */
export function AppealFigures({ figures }: Readonly<{ figures: Figures }>) {
  const items: [string, string][] = [
    ["Open", String(figures.open)],
    ["Upheld", String(figures.upheld)],
    ["Not upheld", String(figures.not_upheld)],
    [
      "Upheld share of those decided",
      figures.upheld_share === null ? "–" : formatShare(figures.upheld_share),
    ],
    ["Redress paid", formatMoney(figures.redress_paid)],
    ["Redress waiting", formatMoney(figures.redress_waiting)],
  ];
  return (
    <dl className="figures">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd className="mono">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
