// Takes the pictures for the user guide from the running app: `npm run guide`.
// Needs `npm run dev` on a freshly seeded database. Passwords come from .env.
import { chromium } from "@playwright/test";
import type { Browser, Page } from "@playwright/test";
import {
  ask,
  scrollTo,
  sidebarOf,
  spent,
  text,
  waitForTurn,
} from "./guide/copilot.ts";
import type { Sidebar } from "./guide/copilot.ts";
import { compare, removeExtra, shoot } from "./guide/pictures.ts";

const APP = "http://localhost:5173";
const VIEWPORT = { width: 1280, height: 800 };
const TALL = { width: 1280, height: 1100 };
const PASSWORD = process.env.HANDLER_PASSWORD ?? "";
const made = new Set<string>();
let spend = 0n;

async function take(
  page: Page,
  name: string,
  part?: Sidebar,
  scroll = false,
  card?: string,
): Promise<void> {
  if (part && scroll) await scrollTo(part, card);
  for (const file of await shoot(page, name, part?.panel)) made.add(file);
  console.log(`  ${name}`);
}

async function signIn(page: Page, who: string): Promise<void> {
  await page.goto(APP);
  await page.getByLabel("Email address").fill(`${who}@undercover.example`);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Sign out" }).waitFor();
}

async function open(
  page: Page,
  path: string,
  ready: string,
  table = false,
): Promise<void> {
  spend += await spent(sidebarOf(page));
  await page.goto(`${APP}${path}`);
  await page.getByText(ready).first().waitFor();
  if (table) await page.locator("tbody tr").first().waitFor();
  await page.waitForTimeout(800);
}

/** The claim numbers in the Copilot's answer, in the order it gave them. */
function claimsIn(answer: string): string[] {
  return [...new Set(answer.match(/CLM-\d+/g) ?? [])];
}

async function question(side: Sidebar, q: string, card?: string) {
  const before = await ask(side, q);
  await waitForTurn(side, before, card);
}

async function dispatch(page: Page, side: Sidebar): Promise<string[]> {
  const before = await ask(
    side,
    "Work the queue with 10 agents and tell me what needs me",
  );
  await side.panel.getByText("start_dispatch").waitFor();
  await take(page, "copilot-steps", side);
  await waitForTurn(side, before);
  await take(page, "copilot-answer", side, true);
  await page.getByRole("link", { name: "Queue" }).click();
  await page.waitForTimeout(1_000);
  await take(page, "queue");
  return claimsIn(await text(side));
}

async function claimPictures(page: Page, held: string): Promise<void> {
  await open(page, `/claims/${held}`, "What the agent did");
  await take(page, "claim");
}

async function handlerWork(page: Page, side: Sidebar, ids: string[]) {
  const [held, back, referred] = [ids[0], ids[1], ids.at(-1)];
  if (!held || !back || !referred || ids.length < 3) {
    throw new Error(`Too few claims need a handler to show: ${ids.join(", ")}`);
  }
  await claimPictures(page, held);
  await question(side, `Why does ${referred} need me?`);
  const note = "Please look again at the cover for the items on this claim";
  await question(side, `Send ${back} back with a note: ${note}`);
  await open(page, `/claims/${back}`, "Sent back by");
  await page
    .getByRole("heading", { name: "A decision sent back" })
    .first()
    .evaluate((el) => {
      el.scrollIntoView({ block: "start" });
    });
  await page.waitForTimeout(1_000);
  await take(page, "decision");
  await question(side, `Sign off on ${held}`, "Confirm the sign-off");
  await page.setViewportSize(TALL);
  await take(page, "copilot-confirm", side, true, "Confirm the sign-off");
  await page.setViewportSize(VIEWPORT);
  await page.getByRole("button", { name: "Cancel" }).click();
  return held;
}

/** Run an evaluation of the five tiny held-out claims and wait until it has finished. */
async function evaluate(page: Page): Promise<void> {
  await page.getByRole("combobox").selectOption("held_out");
  await page.getByLabel("Only the 5 tiny claims").check();
  await page.getByRole("button", { name: "Start an evaluation" }).click();
  const row = page.getByRole("row").filter({ hasText: "held-out set, tiny" });
  await row.getByText("finished").waitFor({ timeout: 600_000 });
}

async function pages(page: Page): Promise<void> {
  await open(page, "/scoreboard", "The scoreboard");
  await evaluate(page);
  await page.setViewportSize({ width: 1600, height: VIEWPORT.height });
  await take(page, "scoreboard");
  await page.setViewportSize(VIEWPORT);
  await open(page, "/improvement", "Improvement");
  await take(page, "improvement");
  await open(page, "/configuration", "Configuration", true);
  await take(page, "configuration");
  await open(page, "/settings", "Settings", true);
  await take(page, "settings");
}

async function appealPictures(page: Page): Promise<void> {
  await open(page, "/appeals", "Appeals to the ombudsman", true);
  await take(page, "appeals");
  await open(page, "/claims/CLM-1602", "An appeal to the ombudsman");
  await page
    .getByRole("heading", { name: /An appeal to the ombudsman/ })
    .evaluate((el) => {
      el.scrollIntoView({ block: "start" });
    });
  await page.waitForTimeout(1_000);
  await take(page, "claim-appeal");
}

async function refusal(browser: Browser, held: string): Promise<void> {
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  await signIn(page, "marcus.oyelaran");
  const side = sidebarOf(page);
  await question(side, `Sign off on ${held}`);
  await take(page, "copilot-refusal", side);
  spend += await spent(side);
  await context.close();
}

async function main(): Promise<void> {
  if (!PASSWORD) throw new Error("HANDLER_PASSWORD isn't set: see .env");
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  await page.goto(APP);
  await page
    .getByLabel("Email address")
    .fill("dana.whitfield@undercover.example");
  await take(page, "signin");
  await signIn(page, "dana.whitfield");
  const side = sidebarOf(page);
  await side.panel.getByText("What needs a handler?").waitFor();
  await take(page, "copilot-sidebar");
  await appealPictures(page);
  const ids = await dispatch(page, side);
  const held = await handlerWork(page, side, ids);
  await pages(page);
  spend += await spent(side);
  await refusal(browser, held);
  await browser.close();
  report(spend);
}

function report(total: bigint): void {
  const { missing, extra } = compare(made);
  if (missing.length)
    console.log(`Not made, but the page names: ${missing.join(", ")}`);
  if (extra.length) {
    console.log(`Removed, as the page doesn't name them: ${extra.join(", ")}`);
    removeExtra(extra);
  }
  const dollars = (Number(total) / 1_000_000).toFixed(4);
  console.log(`The Copilot's turns cost about $${dollars}`);
  console.log(
    "The dispatch and the evaluation's costs are on the queue and the Scoreboard.",
  );
  if (missing.length) process.exitCode = 1;
}

await main();
