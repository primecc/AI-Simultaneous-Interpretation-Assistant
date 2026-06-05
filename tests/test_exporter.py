from simultaneous_interpreter.models import SubtitleSegment, SubtitleStatus
from simultaneous_interpreter.services.exporter import export_srt, export_txt


def test_export_txt_contains_source_and_translation() -> None:
    segments = [
        SubtitleSegment(
            segment_id="seg-1",
            source_text="Hello world.",
            translated_text="你好，世界。",
            status=SubtitleStatus.final,
        )
    ]

    text = export_txt(segments)

    assert "Hello world." in text
    assert "你好，世界。" in text


def test_export_srt_formats_timestamps() -> None:
    segments = [
        SubtitleSegment(
            segment_id="seg-1",
            source_text="Hello world.",
            translated_text="你好，世界。",
            status=SubtitleStatus.final,
            start_ms=1200,
            end_ms=4560,
        )
    ]

    srt = export_srt(segments)

    assert "00:00:01,200 --> 00:00:04,560" in srt
    assert "Hello world." in srt
