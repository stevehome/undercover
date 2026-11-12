# Process

`uv sync` and `npm install` at the repo root install everything, including a git pre-commit hook. `npm run dev` starts the backend, the agent's service and the dashboard, with the variables in `.env`. `npm run seed` resets the database to the seeded queue; stop `npm run dev` first.

`npm run check` runs every check, and needs no Supabase, Langfuse or OpenRouter, so it passes with `.env` moved out of the way:

- Python: ruff (lint and format), pyright, and pytest with 80% coverage
- TypeScript: ESLint, Prettier, tsc, and vitest with 80% coverage
- Playwright end-to-end tests

The pre-commit hook runs the format, lint, type and unit test checks on every commit.

## Planning

When asked to plan, as in "Please plan the pilot", write the plan to `docs/PLAN.md` and write no code.

- Split the work into phases, usually 5 or 6, each building on the last.
- Name the modules each phase adds or changes and the one job of each, following the structure rules in `docs/CODE_STANDARDS.md`. A plan that puts several jobs in one module, or names a module `main.py` for work other than starting the app, is not ready. Write instructions for an agent as a goal, not as steps.
- Give each phase detailed success criteria that you can verify yourself: tests that pass, commands and their output, API calls and their responses, and pages you check in the browser with the Playwright MCP server. Write each one as a checkbox.
- Then stop and wait until you are asked to implement the plan.

## Implementing

When asked to implement the plan, as in "Please implement the plan for the pilot", build every phase in order without stopping. For each phase:

1. Build it, with tests.
2. Check every success criterion and fix whatever fails.
3. Review your own diff as a pull request reviewer would, with the checklist at the end of `docs/CODE_STANDARDS.md`, and fix what you find. Green checks are not a review.
4. Tick off its criteria in `docs/PLAN.md` and update `docs/STATUS.md`.
5. Commit. The pre-commit hook runs the checks; if it fails, fix the problem and commit again.

When the last phase is done, review the whole change once more against the checklist in `docs/CODE_STANDARDS.md`, including the code the build touched outside its own area, then run `npm run check` and report the results.

## Rules

- A passing check proves the code works, not that it is well made. The structure rules in `docs/CODE_STANDARDS.md` apply to every change, and the ones a machine can check live in `agent/tests/test_structure.py` and `eslint.config.js`. When you find a new way for code to be bad that no check catches, add the check or the rule in the same change.
- Add tests with each change. Tests never call a model, the end-to-end tests included: use a stub model, or test the screens with data already in place.
- For any live run with a real model, reseed first, once. Ask the student to run `npm run seed` with `npm run dev` stopped, since the agent may not.
- For browser checks as a handler, sign in as Dana Whitfield or Marcus Oyelaran with `HANDLER_PASSWORD` from `.env`, and keep the password out of the transcript. If it holds `#`, quote it in `.env`.
- The end-to-end tests run their own servers on other ports (backend 8010, dashboard 5183, stand-ins 8003, 8004 and 8005), so `npm run dev` can stay up while they run. Keep to the runs the brief asks for: otherwise a dispatch works the queue, so cap it by working one claim (`uv run -m agent CLM-1001`), or run an evaluation on a set's five `tiny` claims.
- When a build changes the agent, run it on one claim with a real model before you hand the work over, with `MODEL_NAME=openrouter/free` unless asked otherwise, and report what it decided. This is a check by hand, not a test.
- Outside a plan, commit each change once you have checked it.
- Run `npm run check` before you hand work over.
- Never use `git commit --no-verify`.
- Never lower a threshold, turn off a rule or exclude a file to get a green run. If a rule looks wrong, stop and ask.
- Keep `docs/STATUS.md` up to date.
- Never push.
- Don't open `data/evals/` unless you're asked to.
- Everything must work on Windows: write `package.json` scripts as `uv run` commands or `.mjs` files.
