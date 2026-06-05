from simultaneous_interpreter.services.system_audio_translator import SystemAudioTranslator


def test_system_audio_translator_no_longer_requires_openai_key() -> None:
    from simultaneous_interpreter.config import Settings

    settings = Settings()

    readiness = SystemAudioTranslator.check_readiness(settings)

    assert readiness.ready
    assert "无需 API key" in readiness.detail
    assert "OPENAI" not in readiness.detail.upper()
