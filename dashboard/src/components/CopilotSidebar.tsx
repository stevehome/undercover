import { useCallback, useEffect, useState } from "react";
import { fetchConversations } from "../api";
import {
  saveConversation,
  saveOpen,
  savedConversation,
  savedOpen,
} from "../sidebarPreference";
import type { ConversationSummary, Handler } from "../types";
import { useCopilot } from "../useCopilot";
import { Chevron, CopilotMark } from "./CopilotIcons";
import { Composer } from "./Composer";
import { Conversation } from "./Conversation";
import { ConversationList } from "./ConversationList";

/**
 * The Copilot, beside every page: a conversation with the steps it took as cards, the
 * earlier conversations, and a message box. It collapses to a slim tab, remembered by
 * the browser, and on a narrow window it opens over the page.
 */
export function CopilotSidebar({ me }: Readonly<{ me: Handler }>) {
  const [open, setOpen] = useState(savedOpen);
  const [id, setId] = useState<string | null>(savedConversation);
  const [earlier, setEarlier] = useState<ConversationSummary[]>([]);
  const chat = useCopilot(id, (made) => {
    setId(made);
  });

  const pick = useCallback((picked: string | null) => {
    setId(picked);
    saveConversation(picked);
  }, []);
  const toggle = () => {
    saveOpen(!open);
    setOpen(!open);
  };

  const title = chat.conversation?.title;
  useEffect(() => {
    if (id !== null) saveConversation(id);
    fetchConversations().then(setEarlier, () => {
      setEarlier([]);
    });
  }, [id, title]);

  if (!open) {
    return (
      <aside className="copilot collapsed" aria-label="Copilot">
        <button
          type="button"
          className="copilot-tab"
          aria-label="Open the Copilot"
          onClick={toggle}
        >
          <Chevron pointsRight={false} />
          <CopilotMark />
        </button>
      </aside>
    );
  }
  return (
    <aside className="copilot" aria-label="Copilot">
      <header className="copilot-head">
        <CopilotMark />
        <h2>Copilot</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Collapse the Copilot"
          onClick={toggle}
        >
          <Chevron pointsRight />
        </button>
      </header>
      <ConversationList conversations={earlier} current={id} onPick={pick} />
      <div className="copilot-body">
        <Conversation
          conversation={chat.conversation}
          me={me}
          onAsk={(text) => void chat.send(text)}
          onAnswer={(confirmed) => void chat.answer(confirmed)}
        />
      </div>
      {chat.problem !== null && (
        <p className="copilot-problem" role="alert">
          {chat.problem}
        </p>
      )}
      <Composer
        status={chat.conversation?.status ?? null}
        onSend={(text) => void chat.send(text)}
      />
      <footer className="copilot-foot">Signed in as {me.name}</footer>
    </aside>
  );
}
