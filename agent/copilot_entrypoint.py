"""The UnderCover Copilot as an AgentCore app: the one entrypoint Runtime calls."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from starlette.responses import JSONResponse

from agent import copilot_operations
from agent.background_work import BackgroundWork

app = BedrockAgentCoreApp()
background = BackgroundWork(app.add_async_task, app.complete_async_task)


@app.entrypoint
def invoke(payload: object) -> JSONResponse:
    """Answer a payload: the operation it names, with the sign-in it came with."""
    answer = copilot_operations.handle(payload, background)
    return JSONResponse(answer.body, status_code=answer.status)
