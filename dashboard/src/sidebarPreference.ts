/** What the Copilot's sidebar remembers in this browser: whether it is open, and which
 * conversation it was showing. It is open the first time. */
const OPEN_KEY = "undercover-copilot-open";
const CONVERSATION_KEY = "undercover-copilot-conversation";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // The sidebar still works; this browser just won't remember it.
  }
}

export const savedOpen = (): boolean => read(OPEN_KEY) !== "false";

export const saveOpen = (open: boolean) => {
  write(OPEN_KEY, String(open));
};

export const savedConversation = (): string | null => read(CONVERSATION_KEY);

export const saveConversation = (id: string | null) => {
  write(CONVERSATION_KEY, id);
};
