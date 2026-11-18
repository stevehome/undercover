/** The agent's API key for the test backend; playwright.config.ts gives it the same one. */
export const agentKey = "e2e-agent-key";

/** The headers of a request the agent would make. */
export const agentHeaders = { "X-API-Key": agentKey };
