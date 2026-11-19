import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import dashboard_files


@pytest.fixture
def built(tmp_path):
    """A stand-in for a built dashboard, and a secret file beside it."""
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text("<html>the dashboard</html>")
    (folder / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("secret")
    return folder


@pytest.fixture
def client(built):
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, str]:
        return {"ping": "pong"}

    dashboard_files.serve(app, built)
    return TestClient(app)


def test_the_root_and_a_dashboard_page_get_index_html(client):
    assert "the dashboard" in client.get("/").text
    assert "the dashboard" in client.get("/claims/CLM-1001").text


def test_a_file_is_served_at_its_own_path(client):
    assert client.get("/assets/app.js").text == "console.log('app')"


def test_an_api_route_is_still_answered(client):
    assert client.get("/api/ping").json() == {"ping": "pong"}


def test_an_unknown_api_path_is_a_json_404(client):
    response = client.get("/api/nothing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_a_path_out_of_the_folder_gets_index_html_not_the_file(client):
    response = client.get("/%2e%2e/secret.txt")
    assert "secret" not in response.text
    assert "the dashboard" in response.text


def test_nothing_is_served_with_no_build(tmp_path):
    app = FastAPI()
    dashboard_files.serve(app, tmp_path / "missing")
    assert TestClient(app).get("/").status_code == 404
