import { formatGrade, formatShare } from "../measures";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";

export interface VersionPoint {
  version: number;
  accuracy: number | null;
  grade: number | null;
}

const WIDTH = 560;
const HEIGHT = 220;
const PAD = { left: 48, right: 48, top: 16, bottom: 32 };
const MAX_GRADE = 3;

const x = (index: number, count: number) =>
  PAD.left +
  (count === 1 ? 0.5 : index / (count - 1)) * (WIDTH - PAD.left - PAD.right);
const y = (share: number) =>
  PAD.top + (1 - share) * (HEIGHT - PAD.top - PAD.bottom);

function line(values: (number | null)[], scale: number): string {
  return values
    .flatMap((value, index) =>
      value === null
        ? []
        : [`${String(x(index, values.length))},${String(y(value / scale))}`],
    )
    .join(" ");
}

/** The held-out accuracy and grade of each version tried, in SVG with a table of the numbers. */
export function VersionChart({ points }: Readonly<{ points: VersionPoint[] }>) {
  if (points.length === 0) {
    return (
      <EmptyState>
        No version has been evaluated on the held-out set yet. A round does it.
      </EmptyState>
    );
  }
  const accuracy = points.map((point) => point.accuracy);
  const grade = points.map((point) => point.grade);
  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
        role="img"
        aria-label="Held-out accuracy and grade of each version tried"
      >
        {[0, 0.5, 1].map((tick) => (
          <g key={tick}>
            <line
              className="gridline"
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={y(tick)}
              y2={y(tick)}
            />
            <text
              className="axis"
              x={PAD.left - 6}
              y={y(tick) + 4}
              textAnchor="end"
            >
              {formatShare(tick)}
            </text>
            <text className="axis" x={WIDTH - PAD.right + 6} y={y(tick) + 4}>
              {(tick * MAX_GRADE).toFixed(1)}
            </text>
          </g>
        ))}
        <polyline
          className="series-accuracy"
          fill="none"
          points={line(accuracy, 1)}
        />
        <polyline
          className="series-grade"
          fill="none"
          points={line(grade, MAX_GRADE)}
        />
        {points.map((point, index) => (
          <g key={point.version}>
            <text
              className="axis"
              x={x(index, points.length)}
              y={HEIGHT - 10}
              textAnchor="middle"
            >
              v{point.version}
            </text>
            {point.accuracy !== null && (
              <circle
                className="mark-accuracy"
                cx={x(index, points.length)}
                cy={y(point.accuracy)}
                r={5}
              />
            )}
            {point.grade !== null && (
              <rect
                className="mark-grade"
                x={x(index, points.length) - 5}
                y={y(point.grade / MAX_GRADE) - 5}
                width={10}
                height={10}
              />
            )}
          </g>
        ))}
      </svg>
      <figcaption>
        <span className="key key-accuracy">● Accuracy (left axis)</span>{" "}
        <span className="key key-grade">■ Grade, 0 to 3 (right axis)</span>
      </figcaption>
      <details>
        <summary>The same numbers in a table</summary>
        <DataTable>
          <thead>
            <tr>
              <th className="number">Version</th>
              <th className="number">Accuracy</th>
              <th className="number">Grade</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.version}>
                <td className="number">{point.version}</td>
                <td className="number">
                  {point.accuracy === null ? "–" : formatShare(point.accuracy)}
                </td>
                <td className="number">{formatGrade(point.grade)}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </details>
    </figure>
  );
}
