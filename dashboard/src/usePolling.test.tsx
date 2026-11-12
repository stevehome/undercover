import { act, cleanup, render, screen } from "@testing-library/react";
import { useCallback, useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { usePolling } from "./usePolling";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function Probe({
  fetchNumber,
}: Readonly<{ fetchNumber: () => Promise<number> }>) {
  const [value, setValue] = useState<number | null>(null);
  const load = useCallback(() => fetchNumber().then(setValue), [fetchNumber]);
  const failed = usePolling(load, true);
  return (
    <p>
      {value === null ? "nothing" : `value ${String(value)}`}
      {failed ? " (failed)" : ""}
    </p>
  );
}

it("keeps the data it has when a later poll fails, and recovers", async () => {
  const replies = [
    () => Promise.resolve(7),
    () => Promise.reject(new Error("down")),
    () => Promise.resolve(8),
  ];
  const fetchNumber = vi.fn(() => (replies.shift() ?? replies[0])());
  render(<Probe fetchNumber={fetchNumber} />);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(screen.getByText("value 7")).toBeDefined();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(screen.getByText("value 7 (failed)")).toBeDefined();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(screen.getByText("value 8")).toBeDefined();
});

it("does not start a poll while the last one is still waiting", async () => {
  const releases: ((n: number) => void)[] = [];
  const fetchNumber = vi.fn(
    () =>
      new Promise<number>((resolve) => {
        releases.push(resolve);
      }),
  );
  render(<Probe fetchNumber={fetchNumber} />);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000);
  });
  expect(fetchNumber).toHaveBeenCalledTimes(1);

  await act(async () => {
    releases[0]?.(5);
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(fetchNumber).toHaveBeenCalledTimes(2);
});
