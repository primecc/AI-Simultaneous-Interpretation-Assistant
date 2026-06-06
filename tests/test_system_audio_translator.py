from simultaneous_interpreter.services.system_audio_translator import (
    RealtimeCorrectionMemory,
    SystemAudioTranslator,
    polish_chinese_translation,
)


class FailingTranslator:
    def translate(self, _text: str) -> str:
        raise RuntimeError("HTTPSConnectionPool(host='translate.google.com') SSLEOFError")


def test_system_audio_translator_no_longer_requires_openai_key() -> None:
    from simultaneous_interpreter.config import Settings

    settings = Settings()

    readiness = SystemAudioTranslator.check_readiness(settings)

    assert readiness.ready
    assert "无需 API key" in readiness.detail
    assert "OPENAI" not in readiness.detail.upper()


def test_translation_polish_makes_output_more_spoken() -> None:
    polished = polish_chinese_translation("因此，您可以进行使用", "therefore you can use it")

    assert polished == "所以，可以使用。"


def test_realtime_memory_marks_similar_updates_as_corrections() -> None:
    memory = RealtimeCorrectionMemory()

    first = memory.upsert("large language motors", "大型语言马达。")
    corrected = memory.upsert("large language models", "大语言模型。")

    assert first is not None
    assert corrected is not None
    assert corrected.segment_id == first.segment_id
    assert corrected.status == "corrected"
    assert corrected.revision == 2


def test_realtime_memory_skips_exact_duplicate() -> None:
    memory = RealtimeCorrectionMemory()

    first = memory.upsert("hello world", "你好世界。")
    duplicate = memory.upsert("hello world", "你好世界。")

    assert first is not None
    assert duplicate is None


def test_translation_network_failure_reports_status_without_raising() -> None:
    from simultaneous_interpreter.config import Settings

    statuses: list[tuple[str, str]] = []
    translator = SystemAudioTranslator(
        settings=Settings(),
        on_result=lambda _result: None,
        on_status=lambda title, detail: statuses.append((title, detail)),
    )

    translated = translator._translate_or_report(FailingTranslator(), "hello")

    assert translated is None
    assert statuses[-1][0] == "翻译网络暂时不可用"
    assert "继续监听" in statuses[-1][1]
