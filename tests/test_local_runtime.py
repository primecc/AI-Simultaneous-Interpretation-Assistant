from simultaneous_interpreter.config import Settings
from simultaneous_interpreter.services import local_runtime
from simultaneous_interpreter.services.local_runtime import (
    ResilientTextTranslator,
    _resolve_asr_model,
    transcribe_segments,
    translate_text,
)


class MissingVadModel:
    def __init__(self) -> None:
        self.vad_values: list[bool] = []

    def transcribe(self, *_args: object, **kwargs: object) -> tuple[list[object], object]:
        vad_filter = bool(kwargs["vad_filter"])
        self.vad_values.append(vad_filter)
        if vad_filter:
            raise RuntimeError("silero_vad_v6.onnx failed: File doesn't exist")
        return [], object()


class BrokenTranslator:
    def translate(self, _text: str) -> str:
        raise RuntimeError("translate.google.com SSL EOF")


class WorkingTranslator:
    def translate(self, text: str) -> str:
        assert text == "hello"
        return "你好"


def test_transcribe_segments_retries_without_vad_when_asset_is_missing() -> None:
    model = MissingVadModel()

    segments = transcribe_segments(model, "sample.wav", Settings())

    assert segments == []
    assert model.vad_values == [True, False]


def test_default_asr_model_prefers_bundled_model(monkeypatch, tmp_path) -> None:
    model_dir = tmp_path / "models" / "faster-whisper-tiny.en"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").write_bytes(b"model")
    monkeypatch.setattr(local_runtime, "_resource_root", lambda: tmp_path)

    assert _resolve_asr_model(Settings(local_asr_model="tiny.en")) == str(model_dir)


def test_default_asr_model_ignores_incomplete_bundled_model(monkeypatch, tmp_path) -> None:
    model_dir = tmp_path / "models" / "faster-whisper-tiny.en"
    model_dir.mkdir(parents=True)
    monkeypatch.setattr(local_runtime, "_resource_root", lambda: tmp_path)

    assert _resolve_asr_model(Settings(local_asr_model="tiny.en")) == "tiny.en"


def test_resilient_translator_falls_back_after_google_failure() -> None:
    translator = ResilientTextTranslator(
        [
            ("Google", BrokenTranslator()),
            ("MyMemory", WorkingTranslator()),
        ]
    )

    assert translate_text(translator, "hello") == "你好"
