from simultaneous_interpreter.services.semantic_segmenter import SemanticTextSegmenter


def test_segmenter_waits_when_fragment_has_weak_ending() -> None:
    segmenter = SemanticTextSegmenter()

    assert segmenter.push("The key is not only") == []
    ready = segmenter.push("speed but also correction.")

    assert [segment.text for segment in ready] == [
        "The key is not only speed but also correction."
    ]


def test_segmenter_flushes_on_pause_after_complete_clause() -> None:
    segmenter = SemanticTextSegmenter()

    assert segmenter.push("We should make the product easier to use") == []
    ready = segmenter.flush_on_pause()

    assert ready is not None
    assert ready.text == "We should make the product easier to use"
    assert ready.reason == "pause"


def test_segmenter_keeps_short_terminal_fragment_until_pause() -> None:
    segmenter = SemanticTextSegmenter()

    assert segmenter.push("Thank you.") == []
    ready = segmenter.flush_on_pause()

    assert ready is not None
    assert ready.text == "Thank you."
