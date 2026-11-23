"""The UnderCover Agent as an AgentCore app: the one entrypoint Runtime calls."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from starlette.responses import JSONResponse

from agent import operations
from agent.background_work import BackgroundWork

app = BedrockAgentCoreApp()
background = BackgroundWork(app.add_async_task, app.complete_async_task)


@app.entrypoint
def invoke(payload: object, context: RequestContext) -> JSONResponse:
    """Answer a payload: the operation it names, with the key it came with."""
    headers = context.request_headers or {}
    answer = operations.handle(payload, headers.get("Authorization"), background)
    return JSONResponse(answer.body, status_code=answer.status)
