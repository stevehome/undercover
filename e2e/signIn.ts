import { expect, test as base } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

export const authStandIn = "http://127.0.0.1:8004";
export const password = "e2e-password";

/** Sign a handler in through the dashboard's sign-in page. */
export async function signIn(page: Page, who = "dana.whitfield") {
  await page.goto("/");
  await page.getByLabel("Email address").fill(`${who}@undercover.example`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

/** The headers of a handler's request to the backend, with a token from the stand-in. */
export async function handlerHeaders(
  request: APIRequestContext,
  who = "dana.whitfield",
) {
  const response = await request.post(
    `${authStandIn}/auth/v1/token?grant_type=password`,
    { data: { email: `${who}@undercover.example`, password } },
  );
  const session = (await response.json()) as { access_token: string };
  return { Authorization: `Bearer ${session.access_token}` };
}

/** Playwright's test, with the page already signed in as Dana Whitfield. */
export const test = base.extend({
  page: async ({ page }, use) => {
    await signIn(page);
    await use(page);
  },
});
