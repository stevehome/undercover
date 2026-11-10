import { useCallback, useState } from "react";
import { fetchClaimInstructions } from "../api";
import { LoadError } from "../components/LoadError";
import { usePolling } from "../usePolling";

export function InstructionsPage() {
  const [instructions, setInstructions] = useState("");

  const load = useCallback(
    () => fetchClaimInstructions().then(setInstructions),
    [],
  );
  const failed = usePolling(load, false);

  return (
    <main className="panel">
      <h1>The agent's instructions</h1>
      {failed && <LoadError />}

      <h2>Deciding a claim</h2>
      <pre>{instructions}</pre>
    </main>
  );
}
