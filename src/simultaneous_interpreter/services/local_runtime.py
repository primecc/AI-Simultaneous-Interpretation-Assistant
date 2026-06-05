import sys
from pathlib import Path

from simultaneous_interpreter.config import Settings

SYSTEM_AUDIO_MODULES = ("numpy", "pyaudiowpatch", "faster_whisper", "deep_translator")
MEDIA_INTERPRETER_MODULES = ("faster_whisper", "deep_translator")


def missing_modules(module_names: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for module_name in module_names:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    return missing


def create_whisper_model(settings: Settings) -> object:
    from faster_whisper import WhisperModel

    return WhisperModel(_resolve_asr_model(settings), device="cpu", compute_type="int8")


def create_text_translator(settings: Settings) -> object:
    from deep_translator import GoogleTranslator

    return GoogleTranslator(
        source=_translator_source_code(settings.source_language),
        target=_translator_target_code(settings.target_language),
    )


def whisper_language(settings: Settings) -> str | None:
    language = settings.source_language.strip().lower()
    if not language or language == "auto":
        return None
    return language


def translate_text(translator: object, source_text: str) -> str:
    translated = translator.translate(source_text)  # type: ignore[attr-defined]
    return str(translated or "").strip()


def transcribe_segments(model: object, source: object, settings: Settings) -> object:
    try:
        segments, _info = _transcribe(model, source, settings, vad_filter=True)
    except Exception as exc:
        if not _looks_like_missing_vad_asset(exc):
            raise
        segments, _info = _transcribe(model, source, settings, vad_filter=False)
    return segments


def _transcribe(
    model: object,
    source: object,
    settings: Settings,
    *,
    vad_filter: bool,
) -> tuple[object, object]:
    return model.transcribe(  # type: ignore[attr-defined]
        source,
        language=whisper_language(settings),
        vad_filter=vad_filter,
        beam_size=1,
    )


def _looks_like_missing_vad_asset(exc: Exception) -> bool:
    message = str(exc).lower()
    return "silero_vad" in message and ("no suchfile" in message or "doesn't exist" in message)


def _resolve_asr_model(settings: Settings) -> str:
    configured_model = settings.local_asr_model.strip()
    configured_path = Path(configured_model)
    if _is_complete_model_dir(configured_path):
        return str(configured_path)

    if configured_model == "tiny.en":
        bundled_model = _resource_root() / "models" / "faster-whisper-tiny.en"
        if _is_complete_model_dir(bundled_model):
            return str(bundled_model)

    return configured_model


def _is_complete_model_dir(path: Path) -> bool:
    if path.is_dir():
        return (path / "model.bin").exists()
    return path.exists()


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path.cwd()


def _translator_source_code(language: str) -> str:
    language = language.strip().lower()
    if not language or language == "auto":
        return "auto"
    return language


def _translator_target_code(language: str) -> str:
    normalized = language.strip().lower().replace("_", "-")
    if normalized in {"zh", "cn", "zh-cn", "chinese", "中文"}:
        return "zh-CN"
    if normalized in {"zh-tw", "zh-hk", "traditional-chinese"}:
        return "zh-TW"
    return language
