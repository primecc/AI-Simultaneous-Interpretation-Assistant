from datetime import UTC, datetime

from simultaneous_interpreter.models import SubtitleSegment, SubtitleStatus


class SubtitleStore:
    """In-memory subtitle store with revision-aware correction support."""

    def __init__(self) -> None:
        self._segments: dict[str, SubtitleSegment] = {}

    def upsert(
        self,
        *,
        segment_id: str,
        source_text: str,
        translated_text: str,
        status: SubtitleStatus,
        start_ms: int = 0,
        end_ms: int | None = None,
    ) -> SubtitleSegment:
        existing = self._segments.get(segment_id)
        now = datetime.now(UTC)

        if existing is None:
            segment = SubtitleSegment(
                segment_id=segment_id,
                source_text=source_text,
                translated_text=translated_text,
                status=status,
                start_ms=start_ms,
                end_ms=end_ms,
                created_at=now,
                updated_at=now,
            )
            self._segments[segment_id] = segment
            return segment

        changed_text = (
            existing.source_text != source_text or existing.translated_text != translated_text
        )
        next_status = SubtitleStatus.corrected if changed_text else status
        segment = existing.model_copy(
            update={
                "source_text": source_text,
                "translated_text": translated_text,
                "status": next_status,
                "revision": existing.revision + 1 if changed_text else existing.revision,
                "end_ms": end_ms if end_ms is not None else existing.end_ms,
                "updated_at": now,
            }
        )
        self._segments[segment_id] = segment
        return segment

    def list_segments(self) -> list[SubtitleSegment]:
        return sorted(self._segments.values(), key=lambda item: (item.start_ms, item.segment_id))

    def clear(self) -> None:
        self._segments.clear()
