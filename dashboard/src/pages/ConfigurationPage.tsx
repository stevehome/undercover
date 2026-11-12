import { useCallback, useState } from "react";
import { fetchConfigurationDiff, fetchConfigurations } from "../api";
import { DataTable } from "../components/DataTable";
import { DiffView } from "../components/DiffView";
import { LoadError } from "../components/LoadError";
import { PageHeader } from "../components/PageHeader";
import { formatGrade, formatShare } from "../measures";
import { formatTime } from "../time";
import type { Configuration, ConfigurationDiff } from "../types";
import { usePolling } from "../usePolling";

function ConfigurationDiffPanel({
  diff,
}: Readonly<{ diff: ConfigurationDiff }>) {
  const changed =
    diff.model_before !== null &&
    (diff.model_before !== diff.model_after ||
      diff.reasoning_effort_before !== diff.reasoning_effort_after);
  return (
    <section aria-label={`Version ${String(diff.version)} changes`}>
      <h3>
        {diff.from_version === null
          ? `Version ${String(diff.version)}, the starting instructions`
          : `Version ${String(diff.version)} changed from version ${String(diff.from_version)}`}
      </h3>
      {changed && (
        <p>
          Model and reasoning effort: {diff.model_before} (
          {diff.reasoning_effort_before}) to {diff.model_after} (
          {diff.reasoning_effort_after}).
        </p>
      )}
      <DiffView lines={diff.lines} />
    </section>
  );
}

export function ConfigurationPage() {
  const [versions, setVersions] = useState<Configuration[]>([]);
  const [diff, setDiff] = useState<ConfigurationDiff | null>(null);

  const load = useCallback(() => fetchConfigurations().then(setVersions), []);
  const failed = usePolling(load, false);

  const kept = versions.filter((version) => version.verdict === "kept");
  const current = kept.at(-1);

  return (
    <main className="panel">
      <PageHeader title="Configuration">
        The claim agent's instructions, model and reasoning effort, in versions.
        Each run records the version it worked to.
      </PageHeader>
      {failed && <LoadError />}
      {current && (
        <section>
          <h2>Current version: {current.version}</h2>
          <p>
            {current.model}, reasoning effort {current.reasoning_effort}.
          </p>
          <pre>{current.instructions}</pre>
        </section>
      )}
      <section>
        <h2>Every version</h2>
        <DataTable>
          <thead>
            <tr>
              <th className="number">Version</th>
              <th>Model</th>
              <th>Reasoning effort</th>
              <th>Verdict</th>
              <th className="number">Held-out accuracy</th>
              <th className="number">Held-out grade</th>
              <th>Reason</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {[...versions].reverse().map((version) => (
              <tr key={version.version}>
                <td className="number">{version.version}</td>
                <td className="mono">{version.model}</td>
                <td>{version.reasoning_effort}</td>
                <td>{version.verdict ?? "undecided"}</td>
                <td className="number">
                  {version.held_out.accuracy === null
                    ? "–"
                    : formatShare(version.held_out.accuracy)}
                </td>
                <td className="number">
                  {formatGrade(version.held_out.grade)}
                </td>
                <td>{version.reason}</td>
                <td>{formatTime(version.created_on)}</td>
                <td>
                  <button
                    type="button"
                    onClick={() => {
                      void fetchConfigurationDiff(version.version).then(
                        setDiff,
                      );
                    }}
                  >
                    Show changes
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </section>
      {diff && <ConfigurationDiffPanel diff={diff} />}
    </main>
  );
}
