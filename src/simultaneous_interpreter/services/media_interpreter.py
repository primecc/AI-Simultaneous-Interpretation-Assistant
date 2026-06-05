from collections.abc import Iterator
from pathlib import Path

from simultaneous_interpreter.config import Settings
from simultaneous_interpreter.models import SubtitleStatus, SubtitleUpdate
from simultaneous_interpreter.services.local_runtime import (
    MEDIA_INTERPRETER_MODULES,
    create_text_translator,
    create_whisper_model,
    missing_modules,
    transcribe_segments,
    translate_text,
)
from simultaneous_interpreter.services.subtitle_store import SubtitleStore


class MediaInterpreterUnavailable(RuntimeError):
    pass


class MediaInterpretationPipeline:
    """Transcribe uploaded media locally, then translate each segment without API keys."""

    def __init__(self, store: SubtitleStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    @staticmethod
    def check_readiness() -> None:
        missing = missing_modules(MEDIA_INTERPRETER_MODULES)
        if missing:
            raise MediaInterpreterUnavailable(
                f"缺少依赖：{', '.join(missing)}。请重新安装或重新打包后再试。"
            )

    def stream(self, *, media_id: str, media_path: Path) -> Iterator[SubtitleUpdate]:
        self.check_readiness()
        model = create_whisper_model(self._settings)
        translator = create_text_translator(self._settings)
        segments = transcribe_segments(model, str(media_path), self._settings)

        for index, raw_segment in enumerate(segments, start=1):
            source_text = raw_segment.text.strip()
            if not source_text:
                continue

            translated_text = translate_text(translator, source_text)
            segment = self._store.upsert(
                segment_id=f"{media_id}-{index:04d}",
                source_text=source_text,
                translated_text=translated_text,
                status=SubtitleStatus.final,
                start_ms=int(raw_segment.start * 1000),
                end_ms=int(raw_segment.end * 1000),
            )
            yield SubtitleUpdate(segment=segment)
