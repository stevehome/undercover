# Plan: a user guide for UnderCover

A static web page that shows a handler what each screen of UnderCover is for, with a screenshot and a few sentences for each, in light and dark, published where anyone can read it. It is not in `docs/COPILOT.md` or any brief: you asked for it in chat. Three phases: the page, the script that captures its screenshots from the running app, and the publishing. Nothing here changes the product.

## What I read

The seven documents `AGENTS.md` lists, `docs/PLAN_COPILOT.md` for the plan's shape, `e2e/signIn.ts` and `e2e/copilot.spec.ts` for how a browser signs in and drives the sidebar, and the dashboard's routes in `dashboard/src/App.tsx`. From this session's live run: the screens as they look with the seeded data, and the script that drove them.

## Where I need your call

1. **Where it's hosted: GitHub Pages (recommended).** It's free, public, and the site is a folder of your own repo. Pages can't serve a `guide/` folder directly (only the root or `docs/`), so a small GitHub Actions workflow publishes `guide/`. Vercel or Cloudflare Pages would give nicer URLs and a preview for each change, but they need a new account and a project; S3 with CloudFront is more setup and one more thing to tear down. Say if you'd rather have one of those, and I'd write its settings in place of the workflow.
2. **The guide lives in `guide/`, not `docs/`.** The documents in `docs/` are UnderCover's requirements for the build; this is for the people who use the product.
3. **The pictures are committed.** About 30 PNGs, a few megabytes. The page needs them to be published, and regenerating them takes a running app, a model and about ten cents. The script is how you refresh them after a change.
4. **Real model answers in the Copilot's pictures.** They come from a live run on the default model, as in this session's checks, not from the end-to-end stand-ins, so what the guide shows is what the Copilot really says.
5. **A sign-in page screenshot shows no password and no one's token.** I'd view every picture before committing it, for the token, `.env` values and any AWS account ID or ARN (none should appear: they come from the app on localhost).

## Design

- **One page, plain files.** `guide/index.html`, `guide/guide.css` and `guide/images/`. No build step and no framework: HTML and CSS, and one small inline script for a light/dark switch that starts from the reader's computer setting and remembers the choice in `localStorage`. Both of each picture are in the page; CSS shows the one that matches the theme.
- **A section per screen,** each with a heading, one screenshot, and two or three sentences in the handler's words about what it's for and what to do there. In order: signing in; the queue and starting a dispatch; a claim and what the agent did; the decision, its payout calculation, sign-off and send back; the Scoreboard and an evaluation; the Improvement page; the Configuration page; Settings; the Copilot's sidebar; asking it a question; its step cards; the confirmation card before a sign-off; a refusal; and the five questions to try. The look follows `docs/BRAND.md`, as the dashboard does.
- **The pictures come from a script, not by hand.** `npm run guide` signs in as Dana Whitfield and Marcus Oyelaran on the running app (`npm run dev`, freshly seeded) with a Playwright browser, and writes each picture to `guide/images/` at a fixed window size, once in light and once in dark. The passwords come from `.env` and are never printed or typed anywhere but the sign-in field.
- **The script does what a handler would do** to reach each state: it asks the Copilot to work the queue, runs a held-out evaluation, sends a claim back, and stops at the confirmation card before answering it (the card is the picture; it then cancels, so nothing is paid). It prints what it did and what it spent.
- **A test keeps the page honest.** `backend/tests/test_guide.py` parses `guide/index.html`: every image has alt text and a file, each has its light and dark pair, every section has a heading and a description, and nothing in the page names a token, a password or `localhost`.
- **Publishing is a workflow file you review.** `.github/workflows/guide.yml` publishes `guide/` to GitHub Pages on a push to your default branch that changes it. I don't push; you do, and you turn Pages on once in the repo's settings (Source: GitHub Actions).

## Phase 1: The page

Write `guide/index.html` and `guide/guide.css` with every section's text, the theme switch, and placeholder pictures, so the page can be read and reviewed before any capture.

**Success criteria**

- [x] 1: The page opens from the file with no server, reads well in light and dark and at phone width, and its switch changes the theme and remembers it.
- [x] 2: Every section has a heading, a description in the handler's words and a picture slot with alt text.
- [x] 3: `backend/tests/test_guide.py` passes and fails when an image has no alt text, a file is missing or the page names a token or `localhost`.
- [x] 4: The page and its styles pass `prettier --check` and the code checklist; `docs/STATUS.md` says what it is.

## Phase 2: The capture script

`scripts/guide.ts` and `npm run guide`: sign in, drive the app to each state, and write the pictures.

**Success criteria**

- [x] 1: With `npm run dev` freshly seeded, `npm run guide` writes every picture the page names, in light and dark, and says what it spent.
- [x] 2: The Copilot's pictures show a real answer from the live model to starting a dispatch and asking what needs a handler, the steps while it works, a confirmation card that was cancelled, and Marcus's refusal; no claim is paid.
- [x] 3: Run again, it replaces the pictures and doesn't leave extra ones; a picture the page doesn't name is reported.
- [x] 4: The password is read from `.env` and appears in no output, file or picture.
- [x] 5: I look at every picture, in both themes, for cut-off text, empty states, a token, an `.env` value or an AWS identifier.
- [x] 6: The script passes `npm run check:ts`; it isn't run by `npm run check`, which needs no model, and `docs/STATUS.md` says how to run it.

## Phase 3: Publishing

`.github/workflows/guide.yml`, and the guide's address in `docs/STATUS.md`.

**Success criteria**

- [x] 1: The workflow publishes only `guide/`, on a push to the default branch that changes it, with the permissions Pages needs and no others.
- [x] 2: `docs/STATUS.md` says to turn on Pages (Source: GitHub Actions), what the address will be, and how to refresh the pictures.
- [x] 3: After you push and turn Pages on, I open the address and check the page, its pictures and its theme switch from outside the laptop's files.
- [x] 4: `npm run check` is green; I report what the capture run spent (about ten cents by this session's runs).

## Not for now

A video or animated walkthrough, translations, a search box, a guide per role, and a guide for the Copilot's API or the deployment. It describes what a handler sees, not how it's built.

I stop here, with no code written, until you ask me to implement the plan.
