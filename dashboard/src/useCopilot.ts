import { useCallback, useState } from "react";
import {
  answerConfirmation,
  fetchConversation,
  makeConversation,
  sendMessage,
} from "./api";
import type { Conversation } from "./types";
import { usePolling } from "./usePolling";

const WORKING_POLL_MS = 1000;

/**
 * One conversation: its state, polled about once a second while a turn works and
 * not while it is idle, and what the handler can do with it. With no conversation
 * yet (`id` is null) the first message makes one.
 */
export function useCopilot(id: string | null, onMade: (id: string) => void) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    setConversation(id === null ? null : await fetchConversation(id));
  }, [id]);
  const working = conversation?.status === "working";
  const loadFailed = usePolling(load, working, WORKING_POLL_MS);

  /** Do something to the conversation, show the reason if it is refused, then read it. */
  const attempt = async (action: (id: string) => Promise<void>) => {
    setProblem(null);
    try {
      const current = id ?? (await makeConversation());
      if (id === null) onMade(current);
      await action(current);
      setConversation(await fetchConversation(current));
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "That didn't work");
    }
  };

  return {
    conversation,
    problem,
    loadFailed,
    send: (text: string) => attempt((current) => sendMessage(current, text)),
    answer: (confirmed: boolean) =>
      attempt((current) => answerConfirmation(current, confirmed)),
  };
}
