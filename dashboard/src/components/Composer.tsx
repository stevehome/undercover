import { useState } from "react";
import type { TurnStatus } from "../types";

const WHY_NOT: Partial<Record<TurnStatus, string>> = {
  working: "The Copilot is working",
  "waiting for a confirmation": "Answer the confirmation first",
};

/** The message box. Enter sends and Shift+Enter starts a new line. It is off while
 * the Copilot works and while a confirmation waits, and says why. */
export function Composer({
  status,
  onSend,
}: Readonly<{ status: TurnStatus | null; onSend: (text: string) => void }>) {
  const [text, setText] = useState("");
  const why = status === null ? undefined : WHY_NOT[status];

  const send = () => {
    const trimmed = text.trim();
    if (trimmed === "" || why !== undefined) return;
    onSend(trimmed);
    setText("");
  };

  return (
    <div className="composer">
      <label htmlFor="copilot-message" className="visually-hidden">
        Ask the Copilot
      </label>
      <textarea
        id="copilot-message"
        rows={2}
        value={text}
        disabled={why !== undefined}
        placeholder={why ?? "Ask the Copilot"}
        onChange={(event) => {
          setText(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            send();
          }
        }}
      />
      <button type="button" disabled={why !== undefined} onClick={send}>
        Send
      </button>
    </div>
  );
}
