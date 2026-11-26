import type { ConversationSummary } from "../types";

/** New conversation, and the handler's earlier ones, newest first by their first question. */
export function ConversationList({
  conversations,
  current,
  onPick,
}: Readonly<{
  conversations: ConversationSummary[];
  current: string | null;
  onPick: (id: string | null) => void;
}>) {
  return (
    <nav className="conversation-list" aria-label="Conversations">
      <button
        type="button"
        className="secondary"
        onClick={() => {
          onPick(null);
        }}
      >
        New conversation
      </button>
      <ul>
        {conversations.map((conversation) => (
          <li key={conversation.conversation_id}>
            <button
              type="button"
              className="link"
              aria-current={conversation.conversation_id === current}
              onClick={() => {
                onPick(conversation.conversation_id);
              }}
            >
              {conversation.title ?? "A new conversation"}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
