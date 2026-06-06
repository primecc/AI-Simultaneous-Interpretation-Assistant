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


class FragmentedWhisperModel:
    def transcribe(self, *_args: object, **_kwargs: object) -> tuple[list[object], object]:
        return [
            SimpleNamespace(text="The key is not only", start=1.0, end=2.2),
            SimpleNamespace(text="speed but also correction.", start=2.2, end=4.0),
        ], object()


class FakeTranslator:
    def translate(self, text: str) -> str:
        translations = {
            "Hello from the talk.": "来自演讲的你好。",
            "The key is not only speed but also correction.": "关键不只是速度，还包括纠错能力。",
        }
        return translations[text]


class FakeWindow:
    def __init__(self, *, screen_width: int = 800, screen_height: int = 600) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.geometry_value = ""
        self.alpha_values: list[float] = []
        self.withdrawn = False
        self.destroyed = False
        self.quit_called = False
        self.updated = False
        self.cancelled_jobs: list[str] = []
        self.grab_released = False

    def winfo_screenwidth(self) -> int:
        return self.screen_width

    def winfo_screenheight(self) -> int:
        return self.screen_height

    def geometry(self, value: str) -> None:
        self.geometry_value = value

    def attributes(self, name: str, value: float) -> None:
        if name == "-alpha":
            self.alpha_values.append(value)

    def withdraw(self) -> None:
        self.withdrawn = True

    def destroy(self) -> None:
        self.destroyed = True

    def quit(self) -> None:
        self.quit_called = True

    def update_idletasks(self) -> None:
        self.updated = True

    def after_cancel(self, job: str) -> None:
        self.cancelled_jobs.append(job)

    def grab_release(self) -> None:
        self.grab_released = True


class FakeMenu:
    def __init__(self) -> None:
        self.grab_released = False
        self.unposted = False

    def grab_release(self) -> None:
        self.grab_released = True

    def unpost(self) -> None:
        self.unposted = True


class FakeTranslatorWorker:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


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


def test_media_pipeline_merges_fragments_before_translation(monkeypatch) -> None:
    monkeypatch.setattr(media_interpreter, "missing_modules", lambda _modules: [])
    monkeypatch.setattr(
        media_interpreter,
        "create_whisper_model",
        lambda _settings: FragmentedWhisperModel(),
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
    assert segment.source_text == "The key is not only speed but also correction."
    assert segment.translated_text == "关键不只是速度，还包括纠错能力。"
    assert segment.start_ms == 1000
    assert segment.end_ms == 4000


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


def test_close_hides_and_destroys_all_overlay_windows() -> None:
    app = DesktopOverlayApp.__new__(DesktopOverlayApp)
    app.root = FakeWindow()
    app.caption = FakeWindow()
    app.menu = FakeMenu()
    trail_windows = [FakeWindow(), FakeWindow()]
    app._trail_windows = trail_windows
    app._translator = FakeTranslatorWorker()
    app._active = True
    app._closing = False
    app._launcher_poll_job = "launcher-job"
    app._caption_poll_job = "caption-job"
    app._trail_after_jobs = ["trail-job-1", "trail-job-2"]

    app.close()

    assert app._closing is True
    assert app._active is False
    assert app._translator is None
    assert app.root.withdrawn is True
    assert app.root.destroyed is True
    assert app.root.quit_called is True
    assert app.caption.destroyed is True
    assert all(window.destroyed for window in trail_windows)
    assert app.root.cancelled_jobs == [
        "launcher-job",
        "caption-job",
        "trail-job-1",
        "trail-job-2",
    ]
    assert app._launcher_poll_job is None
    assert app._caption_poll_job is None
    assert app._trail_after_jobs == []
    assert app.menu.unposted is True


def test_frozen_asset_path_points_to_packaged_assets(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert _asset_path("app-icon-64.png") == (
        tmp_path / "simultaneous_interpreter" / "assets" / "app-icon-64.png"
    )
