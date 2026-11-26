import { afterEach, expect, it, vi } from "vitest";
import {
  answerConfirmation,
  fetchConversation,
  makeConversation,
  sendMessage,
} from "./api";
import {
  card,
  conversation,
  conversationToWire,
  step,
} from "./copilotFixtures";
import { renewSignIn } from "./testAuth";

vi.mock("./auth", () => import("./testAuth"));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function serve(body: unknown, status = 200) {
  const fetcher = vi.fn(() =>
    Promise.resolve(new Response(JSON.stringify(body), { status })),
  );
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

it("reads a conversation, with its cost and payout converted", async () => {
  serve(
    conversationToWire(
      conversation({ status: "waiting for a confirmation", card }),
    ),
  );

  const read = await fetchConversation("copilot-1");

  expect(read.card?.payout).toBe(375000);
  expect(read.messages[1].cost_nanos).toBe(624000);
  expect(read.messages[0].cost_nanos).toBeNull();
  expect(read.status).toBe("waiting for a confirmation");
});

it.each([
  [
    "a step of a kind it doesn't know",
    { steps: [{ ...step(), kind: "magic" }] },
  ],
  [
    "a step in a state it doesn't know",
    { steps: [{ ...step(), state: "dreaming" }] },
  ],
  ["a turn in a status it doesn't know", { status: "lost" }],
])("refuses %s", async (_, change) => {
  serve({ ...conversationToWire(conversation()), ...change });

  await expect(fetchConversation("copilot-1")).rejects.toThrow("we don't know");
});

it("makes a conversation", async () => {
  const fetcher = serve({ conversation_id: "copilot-9" });

  expect(await makeConversation()).toBe("copilot-9");
  expect(fetcher).toHaveBeenCalledWith(
    "/api/copilot/conversations",
    expect.objectContaining({ method: "POST" }),
  );
});

it("says why a conversation couldn't be made", async () => {
  serve({ detail: "Sign in to do this" }, 401);

  await expect(makeConversation()).rejects.toThrow("Sign in to do this");
});

it("renews the sign-in before it sends a message", async () => {
  const fetcher = serve({ conversation_id: "copilot-1" });

  await sendMessage("copilot-1", "Hello");

  expect(renewSignIn).toHaveBeenCalledOnce();
  expect(fetcher).toHaveBeenCalledWith(
    "/api/copilot/conversations/copilot-1/messages",
    expect.objectContaining({ body: JSON.stringify({ text: "Hello" }) }),
  );
});

it("renews the sign-in before it sends an answer", async () => {
  const fetcher = serve({ conversation_id: "copilot-1" });

  await answerConfirmation("copilot-1", true);

  expect(renewSignIn).toHaveBeenCalledOnce();
  expect(fetcher).toHaveBeenCalledWith(
    "/api/copilot/conversations/copilot-1/confirmation",
    expect.objectContaining({ body: JSON.stringify({ confirmed: true }) }),
  );
});

it("passes on the reason a message is refused", async () => {
  serve({ detail: "Answer the confirmation first" }, 409);

  await expect(sendMessage("copilot-1", "Hello")).rejects.toThrow(
    "Answer the confirmation first",
  );
});
