import type { Locator, Page } from "@playwright/test";

const TURN_ENDS = /model calls?, \$[\d.]+/g;
const MAX_WAIT_MS = 6 * 60_000;

export interface Sidebar {
  page: Page;
  panel: Locator;
}

export function sidebarOf(page: Page): Sidebar {
  return { page, panel: page.getByRole("complementary", { name: "Copilot" }) };
}

async function endedTurns(side: Sidebar): Promise<number> {
  return ((await side.panel.innerText()).match(TURN_ENDS) ?? []).length;
}

/** Type a question to the Copilot; the turns ended so far are what to wait past. */
export async function ask(side: Sidebar, text: string): Promise<number> {
  const before = await endedTurns(side);
  const box = side.page.getByLabel("Ask the Copilot");
  await box.fill(text);
  await box.press("Enter");
  return before;
}

/** Wait until the turn after `before` has ended, or a card is waiting for an answer. */
export async function waitForTurn(
  side: Sidebar,
  before: number,
  card?: string,
): Promise<void> {
  const end = Date.now() + MAX_WAIT_MS;
  while (Date.now() < end) {
    await side.page.waitForTimeout(2_000);
    if (card && (await side.page.getByRole("region", { name: card }).count())) {
      return;
    }
    if ((await endedTurns(side)) > before) return;
  }
  throw new Error(
    `The Copilot's turn didn't end in ${String(MAX_WAIT_MS / 1000)} s`,
  );
}

/** The text of the sidebar. */
export async function text(side: Sidebar): Promise<string> {
  return side.panel.innerText();
}

/** Dollars such as "0.0004" as millionths of a dollar, whole numbers. */
export function micros(dollars: string): bigint {
  const [whole = "0", cents = ""] = dollars.split(".");
  return BigInt(whole) * 1_000_000n + BigInt(cents.padEnd(6, "0").slice(0, 6));
}

/** The model spend the sidebar shows, in millionths of a dollar, over its turns. */
export async function spent(side: Sidebar): Promise<bigint> {
  const costs = (await text(side)).matchAll(/model calls?, \$([\d.]+)/g);
  return [...costs].reduce((sum, m) => sum + micros(m[1]), 0n);
}

/** Scroll the sidebar's messages to the start of the Copilot's last answer, or to a card. */
export async function scrollTo(side: Sidebar, card?: string): Promise<void> {
  const target = card
    ? side.panel.getByRole("region", { name: card })
    : side.panel.locator(".from-copilot").last();
  await target.evaluate((el) => {
    el.scrollIntoView({ block: "start" });
  });
}
