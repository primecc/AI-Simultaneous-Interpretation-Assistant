from simultaneous_interpreter.models import SubtitleSegment


def export_txt(segments: list[SubtitleSegment]) -> str:
    lines: list[str] = []
    for segment in segments:
        lines.append(segment.source_text)
        lines.append(segment.translated_text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def export_srt(segments: list[SubtitleSegment]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        start = _format_srt_time(segment.start_ms)
        end = _format_srt_time(segment.end_ms or segment.start_ms + 3000)
        blocks.append(
            f"{index}\n{start} --> {end}\n{segment.source_text}\n{segment.translated_text}"
        )
    return "\n\n".join(blocks) + "\n"


def _format_srt_time(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
