from simultaneous_interpreter.models import SubtitleStatus
from simultaneous_interpreter.services.subtitle_store import SubtitleStore


def test_upsert_creates_partial_segment() -> None:
    store = SubtitleStore()

    segment = store.upsert(
        segment_id="seg-1",
        source_text="large language motors",
        translated_text="大型语言马达",
        status=SubtitleStatus.partial,
    )

    assert segment.segment_id == "seg-1"
    assert segment.status == SubtitleStatus.partial
    assert segment.revision == 1


def test_upsert_marks_changed_existing_segment_as_corrected() -> None:
    store = SubtitleStore()
    store.upsert(
        segment_id="seg-1",
        source_text="large language motors",
        translated_text="大型语言马达",
        status=SubtitleStatus.partial,
    )

    segment = store.upsert(
        segment_id="seg-1",
        source_text="large language models",
        translated_text="大语言模型",
        status=SubtitleStatus.final,
    )

    assert segment.status == SubtitleStatus.corrected
    assert segment.revision == 2
    assert segment.source_text == "large language models"


def test_list_segments_orders_by_start_time() -> None:
    store = SubtitleStore()
    store.upsert(
        segment_id="seg-2",
        source_text="second",
        translated_text="第二句",
        status=SubtitleStatus.final,
        start_ms=2000,
    )
    store.upsert(
        segment_id="seg-1",
        source_text="first",
        translated_text="第一句",
        status=SubtitleStatus.final,
        start_ms=1000,
    )

    assert [segment.segment_id for segment in store.list_segments()] == ["seg-1", "seg-2"]
