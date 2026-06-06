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
from simultaneous_interpreter.services.semantic_segmenter import (
    SemanticTextSegment,
    SemanticTextSegmenter,
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
        segmenter = SemanticTextSegmenter()
        pending_start_ms: int | None = None
        last_end_ms = 0
        output_index = 0

        for raw_segment in segments:
            source_text = raw_segment.text.strip()
            if not source_text:
                continue

            if pending_start_ms is None:
                pending_start_ms = int(raw_segment.start * 1000)
            last_end_ms = int(raw_segment.end * 1000)
            for semantic_segment in segmenter.push(source_text):
                output_index += 1
                yield self._make_update(
                    media_id=media_id,
                    index=output_index,
                    source=semantic_segment,
                    translator=translator,
                    start_ms=pending_start_ms,
                    end_ms=last_end_ms,
                )
                pending_start_ms = last_end_ms

        remaining = segmenter.flush_remaining()
        if remaining is not None and pending_start_ms is not None:
            output_index += 1
            yield self._make_update(
                media_id=media_id,
                index=output_index,
                source=remaining,
                translator=translator,
                start_ms=pending_start_ms,
                end_ms=last_end_ms,
            )

    def _make_update(
        self,
        *,
        media_id: str,
        index: int,
        source: SemanticTextSegment,
        translator: object,
        start_ms: int,
        end_ms: int,
    ) -> SubtitleUpdate:
        translated_text = translate_text(translator, source.text)
        segment = self._store.upsert(
            segment_id=f"{media_id}-{index:04d}",
            source_text=source.text,
            translated_text=translated_text,
            status=SubtitleStatus.final,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        return SubtitleUpdate(segment=segment)
