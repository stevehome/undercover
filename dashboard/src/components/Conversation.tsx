import { formatCost } from "../money";
import { SUGGESTIONS } from "../suggestions";
import type { Conversation as Chat, CopilotMessage, Handler } from "../types";
import { AnswerText } from "./AnswerText";
import { ConfirmationCard } from "./ConfirmationCard";
import { StepCard } from "./StepCard";

const firstName = (name: string) => name.split(" ")[0];

function Greeting({
  me,
  onAsk,
}: Readonly<{ me: Handler; onAsk: (text: string) => void }>) {
  return (
    <div className="greeting">
      <h3>Hello, {firstName(me.name)}</h3>
      <p>Ask about the queue, a claim or a customer, or have the agent work.</p>
      <ul>
        {SUGGESTIONS.map((suggestion) => (
          <li key={suggestion}>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                onAsk(suggestion);
              }}
            >
              {suggestion}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Usage({ message }: Readonly<{ message: CopilotMessage }>) {
  if (message.model_calls === null) return null;
  const cost =
    message.cost_nanos === null ? "" : `, ${formatCost(message.cost_nanos)}`;
  const time =
    message.seconds === null ? "" : `, ${message.seconds.toFixed(1)} s`;
  return (
    <small className="usage">
      {message.model_calls} model {message.model_calls === 1 ? "call" : "calls"}
      {cost}
      {time}
    </small>
  );
}

function Message({ message }: Readonly<{ message: CopilotMessage }>) {
  if (message.role === "handler") {
    return <p className="message from-handler">{message.text}</p>;
  }
  return (
    <div className="message from-copilot">
      <AnswerText text={message.text} />
      <Usage message={message} />
    </div>
  );
}

/** The conversation: each message, the cards of the steps its turn took, a working
 * indicator, and the confirmation a turn waits for. An empty one greets the handler. */
export function Conversation({
  conversation,
  me,
  onAsk,
  onAnswer,
}: Readonly<{
  conversation: Chat | null;
  me: Handler;
  onAsk: (text: string) => void;
  onAnswer: (confirmed: boolean) => void;
}>) {
  if (conversation === null || conversation.messages.length === 0) {
    return <Greeting me={me} onAsk={onAsk} />;
  }
  return (
    <div className="conversation" aria-live="polite">
      {conversation.messages.map((message) => (
        <div key={message.id}>
          <Message message={message} />
          {conversation.steps
            .filter((step) => step.message_id === message.id)
            .map((step) => (
              <StepCard key={step.id} step={step} />
            ))}
        </div>
      ))}
      {conversation.status === "working" && (
        <p className="working-indicator" role="status">
          <span className="spinner" aria-hidden="true" /> Working
        </p>
      )}
      {conversation.status === "stopped" && (
        <p className="stopped-note">
          That turn stopped without an answer. Ask again to carry on.
        </p>
      )}
      {conversation.status === "waiting for a confirmation" &&
        conversation.card && (
          <ConfirmationCard card={conversation.card} onAnswer={onAnswer} />
        )}
    </div>
  );
}
