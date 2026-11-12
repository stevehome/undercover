import { afterEach, expect, it } from "vitest";
import { savedAppearance, setAppearance } from "./theme";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

it("sets the page's colors in both directions", () => {
  setAppearance("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");

  setAppearance("light");
  expect(document.documentElement.dataset.theme).toBe("light");

  setAppearance("system");
  expect(document.documentElement.dataset.theme).toBeUndefined();
});

it("remembers the choice for the browser", () => {
  expect(savedAppearance()).toBe("system");

  setAppearance("dark");

  expect(savedAppearance()).toBe("dark");
});

it("shows a choice without remembering it when asked", () => {
  setAppearance("dark", false);

  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(savedAppearance()).toBe("system");
});
