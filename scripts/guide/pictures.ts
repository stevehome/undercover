import { readdirSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import type { Locator, Page } from "@playwright/test";

export const GUIDE = path.join(import.meta.dirname, "..", "..", "guide");
const IMAGES = path.join(GUIDE, "images");
const THEMES = ["light", "dark"] as const;

/** The pictures the guide's page names, as file names. */
export function namedPictures(): string[] {
  const page = readFileSync(path.join(GUIDE, "index.html"), "utf8");
  return [...page.matchAll(/images\/([\w-]+\.png)/g)].map((m) => m[1]);
}

/** Take a picture of the page, or of one part of it, in light and then in dark. */
export async function shoot(
  page: Page,
  name: string,
  part?: Locator,
): Promise<string[]> {
  const made: string[] = [];
  for (const theme of THEMES) {
    await page.emulateMedia({ colorScheme: theme });
    await page.waitForTimeout(400);
    const file = `${name}-${theme}.png`;
    const options = { path: path.join(IMAGES, file) };
    await (part ? part.screenshot(options) : page.screenshot(options));
    made.push(file);
  }
  return made;
}

/** Say which pictures the page names that were not made, and which files it doesn't name. */
export function compare(made: Set<string>): {
  missing: string[];
  extra: string[];
} {
  const named = new Set(namedPictures());
  const onDisk = readdirSync(IMAGES).filter((f) => f.endsWith(".png"));
  return {
    missing: [...named].filter((f) => !made.has(f)),
    extra: onDisk.filter((f) => !named.has(f)),
  };
}

/** Remove the pictures the page doesn't name. */
export function removeExtra(extra: string[]): void {
  for (const file of extra) rmSync(path.join(IMAGES, file));
}
