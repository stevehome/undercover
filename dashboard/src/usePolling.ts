import { useEffect, useState } from "react";

const POLL_MS = 2000;

/**
 * Call `load` now, and every two seconds while `active` is true, skipping a
 * tick while the last call is still waiting so slow answers never overlap.
 * Returns whether the latest call failed.
 */
export function usePolling(
  load: () => Promise<unknown>,
  active: boolean,
): boolean {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let waiting = false;
    const run = () => {
      if (waiting) return;
      waiting = true;
      load()
        .then(
          () => {
            setFailed(false);
          },
          () => {
            setFailed(true);
          },
        )
        .finally(() => {
          waiting = false;
        });
    };
    run();
    if (!active) return;
    const interval = setInterval(run, POLL_MS);
    return () => {
      clearInterval(interval);
    };
  }, [load, active]);

  return failed;
}
