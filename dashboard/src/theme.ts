/** The appearance: light, dark or the computer's, remembered by each browser. */
export type Appearance = "light" | "dark" | "system";

const KEY = "undercover-appearance";

export const APPEARANCES: { value: Appearance; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Same as the computer" },
];

/** The browser's saved choice, or the computer's when it has none. */
export function savedAppearance(): Appearance {
  try {
    const saved = localStorage.getItem(KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

/** Show an appearance on the page and remember it. */
export function setAppearance(appearance: Appearance, remember = true) {
  if (appearance === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = appearance;
  if (!remember) return;
  try {
    localStorage.setItem(KEY, appearance);
  } catch {
    // The choice still shows; this browser just won't remember it.
  }
}
