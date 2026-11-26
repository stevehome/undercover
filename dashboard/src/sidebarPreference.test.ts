import { afterEach, expect, it, vi } from "vitest";
import {
  saveConversation,
  saveOpen,
  savedConversation,
  savedOpen,
} from "./sidebarPreference";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

it("is open the first time", () => {
  expect(savedOpen()).toBe(true);
});

it("remembers it collapsed and open again", () => {
  saveOpen(false);
  expect(savedOpen()).toBe(false);

  saveOpen(true);
  expect(savedOpen()).toBe(true);
});

it("remembers the conversation it showed, and forgets it", () => {
  expect(savedConversation()).toBeNull();

  saveConversation("copilot-1");
  expect(savedConversation()).toBe("copilot-1");

  saveConversation(null);
  expect(savedConversation()).toBeNull();
});

it("still works when the browser won't keep anything", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });

  expect(savedOpen()).toBe(true);
  expect(() => {
    saveOpen(false);
  }).not.toThrow();
});
