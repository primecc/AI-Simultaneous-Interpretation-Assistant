import sys
from pathlib import Path
from types import SimpleNamespace

from simultaneous_interpreter.config import Settings
from simultaneous_interpreter.desktop_overlay import (
    DesktopOverlayApp,
    _asset_path,
    _load_caption_position,
    _save_caption_position,
)
from simultaneous_interpreter.services import media_interpreter
from simultaneous_interpreter.services.media_interpreter import MediaInterpretationPipeline
from simultaneous_interpreter.services.subtitle_store import SubtitleStore


class FakeWhisperModel:
    def transcribe(self, *_args: object, **_kwargs: object) -> tuple[list[object], object]:
        return [SimpleNamespace(text="Hello from the talk.", start=1.0, end=3.5)], object()


class FakeTranslator:
    def translate(self, text: str) -> str:
        assert text == "Hello from the talk."
        return "来自演讲的你好。"


class FakeWindow:
    def __init__(self, *, screen_width: int = 800, screen_height: int = 600) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.geometry_value = ""

    def winfo_screenwidth(self) -> int:
        return self.screen_width

    def winfo_screenheight(self) -> int:
        return self.screen_height

    def geometry(self, value: str) -> None:
        self.geometry_value = value


def test_media_pipeline_streams_real_interpreter_segments(monkeypatch) -> None:
    monkeypatch.setattr(media_interpreter, "missing_modules", lambda _modules: [])
    monkeypatch.setattr(
        media_interpreter,
        "create_whisper_model",
        lambda _settings: FakeWhisperModel(),
    )
    monkeypatch.setattr(
        media_interpreter,
        "create_text_translator",
        lambda _settings: FakeTranslator(),
    )

    pipeline = MediaInterpretationPipeline(SubtitleStore(), Settings())

    updates = list(pipeline.stream(media_id="media-1", media_path=Path("sample.mp4")))

    assert len(updates) == 1
    segment = updates[0].segment
    assert segment.segment_id == "media-1-0001"
    assert segment.source_text == "Hello from the talk."
    assert segment.translated_text == "来自演讲的你好。"
    assert segment.start_ms == 1000
    assert segment.end_ms == 3500


def test_caption_position_round_trips(tmp_path) -> None:
    position_path = tmp_path / "caption-position.json"

    _save_caption_position(position_path, (120, 360))

    assert _load_caption_position(position_path) == (120, 360)


def test_caption_drag_moves_with_pointer_offset() -> None:
    app = DesktopOverlayApp.__new__(DesktopOverlayApp)
    app.root = FakeWindow()
    app.caption = FakeWindow()
    app._caption_drag_start = (10, 10)
    app._caption_drag_offset = (3, 4)
    app._caption_dragged = False
    app._caption_position = None

    app._move_caption_to_pointer(120, 160)

    assert app._caption_dragged is True
    assert app._caption_position == (117, 156)
    assert app.caption.geometry_value == "620x156+117+156"


def test_frozen_asset_path_points_to_packaged_assets(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert _asset_path("app-icon-64.png") == (
        tmp_path / "simultaneous_interpreter" / "assets" / "app-icon-64.png"
    )
