# Deploying changes to AWS

The quickest way to put a change on AWS, whatever the change is. Find what you changed in the table, run its section, and check it. Where everything already exists, as it does for you, each section changes only the code and the settings. Nothing here deletes anything, except the reseed, which empties the database.

The Python in Sections A, B, E and F calls `labs/week3day4_aws.py`, the helper the Day 4 and Day 5 labs use to deploy the app and the context layer. I read it and checked that it imports with your AWS credentials, but I haven't run a deploy with it, so read the output of your first one.

## What lives where

| Piece              | What it is                                                                            | Where its code is                  | Deployed with |
| ------------------ | ------------------------------------------------------------------------------------- | ---------------------------------- | ------------- |
| The app            | Lambda `undercover-app`: the API and the built dashboard                              | `backend/`, `dashboard/`, `data/`  | Section A     |
| The context layer  | Lambda `undercover-context`: the wording, manual and rules                            | `context/`                         | Section B     |
| The two agents     | AgentCore runtimes `agent` and `copilot`, in the stack `AgentCore-undercover-default` | `agent/`, `runtime/`, `agentcore/` | Section C     |
| The database       | Supabase, one database that your laptop and AWS both use                              | `backend/tables.py`, `data/`       | Section D     |
| The Gateway        | `undercover-gateway`, with the app and the context layer as targets, and the Policy   | the app's agent API                | Section E     |
| The app's settings | Environment variables on the app's Lambda                                             | none                               | Section F     |
| The user guide     | GitHub Pages                                                                          | `guide/`                           | Section G     |

## What did I change?

| You changed                                          | Run, in this order |
| ---------------------------------------------------- | ------------------ |
| A table, or the data the seed loads                  | D, then A          |
| `backend/` or `dashboard/`                           | A                  |
| `context/` (the wording, the manual, the YAML files) | B                  |
| `agent/`, `runtime/` or `agentcore/`                 | C                  |
| A route the claim agent uses, or its API document    | A, then E          |
| An environment variable or key                       | F                  |
| `guide/` or `docs/`                                  | G, or nothing      |
| Only tests                                           | nothing            |

The appeals work changed a table, the seed data, the app, the context layer's files and the Copilot, so it needs D, B, A and C, in that order. If the Gateway's targets aren't changing, skip E.

## Before any deploy

- Run `npm run check`. A deploy can't fix a failing test.
- Make sure nothing is running on AWS: no dispatch, evaluation or round, and no Copilot turn waiting on a confirmation you care about. Check the queue page.
- Your AWS credentials are the ones the AWS CLI already uses, in `us-east-1`. Everything below runs from the repo's root folder unless it says otherwise.

## A. The app: `backend/`, `dashboard/`, `data/`

This builds the dashboard, packages it with the backend for Linux, and updates the Lambda's code. The helper in `labs/week3day4_aws.py` does the packaging and the update, so you don't write it again.

```
npm run build
cd labs
uv run python
```

Then, in that Python prompt:

```python
import week3day4_aws as aws
settings = aws.lambda_client.get_function_configuration(FunctionName=aws.APP_FUNCTION)
aws.deploy_app(settings["Environment"]["Variables"])
```

It takes about a minute and prints the app's address. Reading the settings first matters: `deploy_app` sets the Lambda's environment to exactly what it's given, so giving it the current settings keeps every key you already have.

Check it:

```
curl https://<your-app-address>/api/health
```

You should see `{"status":"ok"}`. Then open the dashboard and sign in.

## B. The context layer: `context/`

```
cd labs
uv run python
```

```python
import week3day4_aws as aws
aws.deploy_context()
```

The context layer reads its files when it starts, so a new version is served as soon as the Lambda is updated. The Gateway already points at it, so nothing else changes.

Check it: ask the Copilot, or the dashboard's agent, for a new term, such as "What does redress mean?"

## C. The two agents: `agent/`, `runtime/`, `agentcore/`

Both runtimes are built from one package, so one command deploys both.

```
agentcore deploy
```

It takes 7 to 10 minutes, most of it while Runtime makes its snapshot. It reads `agentcore/.env.local`, which already holds your three credentials and four settings, so don't delete that file. A deploy changes the runtimes' code and settings; the app's Lambda isn't touched, so do A separately if the app changed too.

Check it: `agentcore status` lists both runtimes as ready. Then send the Copilot a message, and wait more than a minute before the second one. The Copilot's runtime keeps its session for 15 minutes, so the second message should not show a 502.

## D. The database: when a table or the seed data changes

```
npm run seed
```

This drops UnderCover's schema in Supabase and builds it again from `data/`. Your laptop's `.env` and the deployed app use the same Supabase database, so this reseeds what AWS uses too, and the Lambda code needs no change to see it. It also empties every claim, run and Copilot conversation, so only do it when nothing is running and you don't need what's there.

New tables only appear this way. The app on Lambda doesn't create tables when it starts, so new code that needs a new table fails until you have reseeded.

Check it: the queue page shows 26 waiting claims, and the pages for any new feature show their starting data.

## E. The Gateway: only when the agent's API changes

The claim agent's API document, `GET /api/agent/openapi.json`, is what the Gateway's app target is built from. If you add, remove or change a route the agent uses, update the target after deploying the app (A):

```
cd labs
uv run python
```

```python
import week3day4_aws as aws
fn = aws.lambda_client.get_function_configuration(FunctionName=aws.APP_FUNCTION)
key = fn["Environment"]["Variables"]["UNDERCOVER_API_KEY"]
app = aws.function_url(aws.APP_FUNCTION, "NONE")
context = aws.function_url(aws.CONTEXT_FUNCTION, "AWS_IAM")
aws.create_gateway(app, context, key)
```

`create_gateway` runs the whole Gateway setup again, as Day 3 did it: it updates the key, the role, the two targets and the Policy, and creates only what is missing. The Gateway's address doesn't change, so the runtimes' settings stay as they are.

The appeals work doesn't touch the agent's API, so it doesn't need this. If you are not sure whether you changed it, run `uv run pytest backend/tests/test_copilot.py -k agents_own_api`: it fails when the agent's operations change.

## F. The app's settings and keys

To change one setting, add it to what is there, and update only the configuration:

```
cd labs
uv run python
```

```python
import week3day4_aws as aws
fn = aws.APP_FUNCTION
variables = aws.lambda_client.get_function_configuration(FunctionName=fn)["Environment"]["Variables"]
variables["SOME_SETTING"] = "its value"
aws.lambda_client.update_function_configuration(FunctionName=fn, Environment={"Variables": variables})
aws.lambda_client.get_waiter("function_updated_v2").wait(FunctionName=fn)
```

Never send a smaller set of variables than you read: it replaces them all. For the runtimes' settings, edit `agentcore/.env.local` and run `agentcore deploy` (C).

## G. The user guide

`git push fork <your-branch>:main` publishes `guide/`, through the Pages workflow, in about 30 seconds. Nothing else on AWS is involved.

## A whole release, in order

1. `npm run check`
2. D, if a table or the seed data changed
3. B, if `context/` changed
4. A, if `backend/`, `dashboard/` or `data/` changed
5. E, only if the agent's API changed
6. C, if `agent/` or `runtime/` changed
7. Check each piece as its section says, then try one thing in the dashboard as Dana Whitfield, and one in the Copilot.

D comes first because the new code expects the new tables. A comes before C because the runtimes call the app.

## When something goes wrong

- **The dashboard shows an error after A:** open the app's logs, `aws logs tail /aws/lambda/undercover-app --since 10m`, and look for a traceback. A missing table is D; a missing key is F.
- **A change doesn't show:** a browser may hold the old dashboard files, so hard refresh. The app's Lambda serves the dashboard it was built with.
- **The Copilot answers with a 502:** wait a few seconds and send it again; the app retries a starting container itself. If it keeps happening, the app's logs have a warning naming the runtime and the session.
- **A deploy changed nothing:** `agentcore deploy` can finish with a warning and no change. Read its last lines, and see `NOTES.md`, which records the CDK version problem that did this once.

## Costs and cleaning up

Updating the Lambdas and the runtimes costs almost nothing. Running them costs real money while they are used, and a dispatch on the default model is a few cents. When you stop testing, the Day 4 and Day 5 labs' teardown cells take everything down, and `uv run monitor.py` shows your AWS spend.
