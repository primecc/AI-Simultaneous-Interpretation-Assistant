import sys
from pathlib import Path
from types import SimpleNamespace

from simultaneous_interpreter.config import Settings
from simultaneous_interpreter.desktop_overlay import (
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


def test_frozen_asset_path_points_to_packaged_assets(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert _asset_path("app-icon-64.png") == (
        tmp_path / "simultaneous_interpreter" / "assets" / "app-icon-64.png"
    )
