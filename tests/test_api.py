from pathlib import Path

from fastapi.testclient import TestClient

from simultaneous_interpreter.main import app, store


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_clear_subtitles_endpoint() -> None:
    client = TestClient(app)
    store.clear()

    response = client.post("/api/subtitles/clear")

    assert response.status_code == 200
    assert response.json() == {"status": "cleared"}


def test_upload_media_endpoint_accepts_video_file() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/media",
        files={"file": ("sample.mp4", b"fake-video-bytes", "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"].endswith(".mp4")
    assert body["url"].startswith("/media/")
    uploaded_path = Path("uploads") / body["filename"]
    if uploaded_path.exists():
        uploaded_path.unlink()


def test_upload_media_endpoint_rejects_unsupported_file() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/media",
        files={"file": ("sample.txt", b"not media", "text/plain")},
    )

    assert response.status_code == 400
