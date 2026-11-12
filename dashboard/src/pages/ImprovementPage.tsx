import { useCallback, useState } from "react";
import {
  fetchConfigurations,
  fetchRecipeDiff,
  fetchRecipes,
  fetchRounds,
  startRound,
  stopRound,
} from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { DiffView } from "../components/DiffView";
import { LoadError } from "../components/LoadError";
import { PageHeader } from "../components/PageHeader";
import { ProposalReview } from "../components/ProposalReview";
import { RoundProgress } from "../components/RoundProgress";
import { RoundsTable } from "../components/RoundsTable";
import { StatusPill } from "../components/StatusPill";
import { VersionChart } from "../components/VersionChart";
import type { VersionPoint } from "../components/VersionChart";
import { formatMoney } from "../money";
import { formatTime } from "../time";
import type { Configuration, DiffLine, Recipe, Round } from "../types";
import { useMe } from "../useMe";
import { usePolling } from "../usePolling";

const CLOSED = ["finished", "stopped"];

const CONFIRMATIONS = {
  start: {
    title: "Start a round?",
    confirm: "Start the round",
    text: "The round first evaluates the current version if it needs it, then the improver works. It spends up to the round's limit in Settings.",
  },
  stop: {
    title: "Stop this round?",
    confirm: "Stop it",
    text: "A round stopped before its verdict leaves the current version as it is. The work in hand ends first.",
  },
};

const chartPoints = (versions: Configuration[]): VersionPoint[] =>
  versions
    .filter((version) => version.held_out.runs > 0)
    .map((version) => ({
      version: version.version,
      accuracy: version.held_out.accuracy,
      grade: version.held_out.grade,
    }));

function RecipeVersions({ recipes }: Readonly<{ recipes: Recipe[] }>) {
  const [shown, setShown] = useState<{
    version: number;
    lines: DiffLine[];
  } | null>(null);
  return (
    <section>
      <h2>The improver's recipe</h2>
      <DataTable>
        <thead>
          <tr>
            <th className="number">Version</th>
            <th>Reason</th>
            <th>Approved by</th>
            <th>Created</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {[...recipes].reverse().map((recipe) => (
            <tr key={recipe.version}>
              <td className="number">{recipe.version}</td>
              <td>{recipe.reason}</td>
              <td>{recipe.approved_by ?? "–"}</td>
              <td>{formatTime(recipe.created_on)}</td>
              <td>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    void fetchRecipeDiff(recipe.version).then(setShown);
                  }}
                >
                  Show changes
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {shown && (
        <section aria-label={`Recipe version ${String(shown.version)} changes`}>
          <h3>Recipe version {shown.version}: what it changed</h3>
          <DiffView lines={shown.lines} />
        </section>
      )}
    </section>
  );
}

function RoundControls({
  canAct,
  name,
  open,
  onAsk,
}: Readonly<{
  canAct: boolean;
  name: string;
  open: Round | undefined;
  onAsk: (action: "start" | "stop") => void;
}>) {
  if (!canAct) {
    return (
      <p>
        {name} can't start or stop a round, or approve its proposals: only a
        handler who can sign off payouts over the limit can.
      </p>
    );
  }
  return (
    <div className="actions">
      <button
        type="button"
        disabled={open !== undefined}
        onClick={() => {
          onAsk("start");
        }}
      >
        Start a round
      </button>
      {open && (
        <button
          type="button"
          className="secondary"
          onClick={() => {
            onAsk("stop");
          }}
        >
          Stop round {open.round_id}
        </button>
      )}
    </div>
  );
}

function CurrentRound({
  round,
  canDecide,
  name,
  onChanged,
}: Readonly<{
  round: Round;
  canDecide: boolean;
  name: string;
  onChanged: () => void;
}>) {
  const pending = round.proposals.find((p) => p.status === "pending");
  return (
    <section aria-label="The round open now">
      <h2>
        Round {round.round_id} <StatusPill status={round.stage} />
      </h2>
      <p>
        Started by {round.started_by_name} at {formatTime(round.started_on)},
        spending up to {formatMoney(round.spending_limit)}.
      </p>
      <RoundProgress round={round} />
      {pending && (
        <ProposalReview
          proposal={pending}
          handlerName={name}
          canDecide={canDecide}
          onDecided={onChanged}
        />
      )}
    </section>
  );
}

export function ImprovementPage() {
  const me = useMe();
  const [rounds, setRounds] = useState<Round[] | null>(null);
  const [versions, setVersions] = useState<Configuration[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [confirming, setConfirming] = useState<"start" | "stop" | null>(null);
  const [message, setMessage] = useState("");
  const canAct = me?.can_approve_over_limit === true;

  const load = useCallback(
    () =>
      Promise.all([fetchRounds(), fetchConfigurations(), fetchRecipes()]).then(
        ([r, v, p]) => {
          setRounds(r);
          setVersions(v);
          setRecipes(p);
        },
      ),
    [],
  );
  const open = rounds?.find((round) => !CLOSED.includes(round.stage));
  const failed = usePolling(load, rounds === null || open !== undefined);

  const confirm = () => {
    const action =
      confirming === "stop" && open ? stopRound(open.round_id) : startRound();
    setConfirming(null);
    setMessage("");
    action.then(load).catch((error: unknown) => {
      setMessage(error instanceof Error ? error.message : "Could not do that.");
    });
  };

  return (
    <main className="panel">
      <PageHeader title="Improvement">
        A round has the improver read the claim agent's results, propose a
        change, and test it. A handler approves each change before it takes
        effect, and the backend keeps or rolls back the new version by the
        business objectives in Settings.
      </PageHeader>
      {failed && <LoadError />}
      {message && <p role="alert">{message}</p>}
      <RoundControls
        canAct={canAct}
        name={me?.name ?? "You"}
        open={open}
        onAsk={setConfirming}
      />
      {open && (
        <CurrentRound
          round={open}
          canDecide={canAct}
          name={me?.name ?? "You"}
          onChanged={() => void load()}
        />
      )}
      <section>
        <h2>Rounds so far</h2>
        <RoundsTable rounds={rounds ?? []} />
      </section>
      <section>
        <h2>Held-out accuracy and grade by version</h2>
        <VersionChart points={chartPoints(versions)} />
      </section>
      <RecipeVersions recipes={recipes} />
      {confirming && (
        <ConfirmDialog
          title={CONFIRMATIONS[confirming].title}
          confirmLabel={CONFIRMATIONS[confirming].confirm}
          onConfirm={confirm}
          onCancel={() => {
            setConfirming(null);
          }}
        >
          <p>{CONFIRMATIONS[confirming].text}</p>
        </ConfirmDialog>
      )}
    </main>
  );
}
