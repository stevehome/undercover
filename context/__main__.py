"""Serve the context layer on the laptop.

uv run -m context
"""

import uvicorn

from context.server import build_server

HOST = "127.0.0.1"
PORT = 8006


def main() -> None:
    uvicorn.run(build_server().streamable_http_app(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
