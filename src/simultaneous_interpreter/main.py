import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from simultaneous_interpreter.config import get_settings
from simultaneous_interpreter.models import HealthResponse, MediaAsset, SubtitleUpdate
from simultaneous_interpreter.services.exporter import export_srt, export_txt
from simultaneous_interpreter.services.media_interpreter import (
    MediaInterpretationPipeline,
    MediaInterpreterUnavailable,
)
from simultaneous_interpreter.services.media_library import MediaLibrary
from simultaneous_interpreter.services.subtitle_store import SubtitleStore

settings = get_settings()
app = FastAPI(title=settings.app_name)
store = SubtitleStore()

STATIC_DIR = Path(__file__).resolve().parent / "static"
UPLOAD_DIR = Path(os.getenv("AI_SI_UPLOAD_DIR", str(Path.cwd() / "uploads"))).resolve()
media_library = MediaLibrary(UPLOAD_DIR)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.app_env)


@app.get("/api/subtitles")
async def list_subtitles() -> list[dict]:
    return [segment.model_dump(mode="json") for segment in store.list_segments()]


@app.post("/api/subtitles/clear")
async def clear_subtitles() -> dict[str, str]:
    store.clear()
    return {"status": "cleared"}


@app.get("/api/media", response_model=list[MediaAsset])
async def list_media() -> list[MediaAsset]:
    return media_library.list_assets()


@app.post("/api/media", response_model=MediaAsset)
async def upload_media(file: Annotated[UploadFile, File()]) -> MediaAsset:
    try:
        return await media_library.save_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/export.txt", response_class=PlainTextResponse)
async def download_txt() -> str:
    return export_txt(store.list_segments())


@app.get("/api/export.srt", response_class=PlainTextResponse)
async def download_srt() -> str:
    return export_srt(store.list_segments())


@app.websocket("/ws/interpret")
async def interpret(websocket: WebSocket, media_id: str | None = None) -> None:
    await websocket.accept()
    if not media_id:
        await websocket.send_json(
            {"event": "status", "state": "error", "message": "请先选择视频或音频。"}
        )
        await websocket.close()
        return

    asset = media_library.find(media_id)
    if asset is None:
        await websocket.send_json(
            {"event": "status", "state": "error", "message": "未找到已导入的媒体文件。"}
        )
        await websocket.close()
        return

    pipeline = MediaInterpretationPipeline(store, settings)
    media_path = UPLOAD_DIR / asset.filename
    try:
        for update in pipeline.stream(media_id=media_id, media_path=media_path):
            await websocket.send_json(_serialize_update(update))
        await websocket.send_json(
            {"event": "status", "state": "idle", "message": "字幕处理完成"}
        )
    except WebSocketDisconnect:
        return
    except MediaInterpreterUnavailable as exc:
        await websocket.send_json({"event": "status", "state": "error", "message": str(exc)})
    except Exception as exc:
        await websocket.send_json(
            {"event": "status", "state": "error", "message": f"字幕处理失败：{exc}"}
        )


def _serialize_update(update: SubtitleUpdate) -> dict:
    return update.model_dump(mode="json")


app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
