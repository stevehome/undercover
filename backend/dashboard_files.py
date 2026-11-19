"""Serves a built dashboard from a folder, for a backend with no web server in front."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

BUILD = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


def serve(app: FastAPI, folder: Path) -> None:
    """Serve the files in a folder, and its `index.html` for any other page.

    Nothing is served when there is no folder, as before the dashboard is built.
    Add it after every other route. A path under `/api/` that no route answers is
    still a JSON 404, not a page.
    """
    if not folder.is_dir():
        return
    root = folder.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def dashboard_file(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (root / path).resolve()
        if file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        return FileResponse(root / "index.html")
