import queue
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher

from simultaneous_interpreter.config import Settings
from simultaneous_interpreter.services.local_runtime import (
    SYSTEM_AUDIO_MODULES,
    create_text_translator,
    create_whisper_model,
    missing_modules,
    transcribe_segments,
    translate_text,
)


@dataclass(frozen=True)
class BackgroundTranslation:
    segment_id: str
    source_text: str
    translated_text: str
    status: str = "final"
    revision: int = 1


@dataclass(frozen=True)
class TranslatorReadiness:
    ready: bool
    title: str
    detail: str


class SystemAudioTranslator:
    """Capture Windows speaker loopback audio and translate it without API keys."""

    def __init__(
        self,
        *,
        settings: Settings,
        on_result: Callable[[BackgroundTranslation], None],
        on_status: Callable[[str, str], None],
    ) -> None:
        self._settings = settings
        self._on_result = on_result
        self._on_status = on_status
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._translation_cache: dict[str, str] = {}
        self._memory = RealtimeCorrectionMemory()

    @staticmethod
    def check_readiness(settings: Settings) -> TranslatorReadiness:
        missing = missing_modules(SYSTEM_AUDIO_MODULES)

        if missing:
            return TranslatorReadiness(
                ready=False,
                title="缺少本地识别/翻译依赖",
                detail=f"缺少依赖：{', '.join(missing)}。请重新安装或重新打包后再试。",
            )

        return TranslatorReadiness(
            ready=True,
            title="后台翻译已就绪",
            detail=(
                "点击后会直接听取电脑正在播放的网页/软件声音。首次运行会自动准备本地识别模型，"
                "无需 API key。"
            ),
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="system-audio-translator",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        audio_backend = None
        stream = None
        try:
            import numpy as np
            import pyaudiowpatch as pyaudio

            audio_backend = pyaudio.PyAudio()
            loopback_device = audio_backend.get_default_wasapi_loopback()
            device_id = int(loopback_device["index"])
            channels = max(1, min(2, int(loopback_device.get("maxInputChannels") or 2)))
            sample_rate = int(float(loopback_device.get("defaultSampleRate") or 48_000))
            frames_per_buffer = max(1, int(sample_rate * self._settings.audio_chunk_seconds))

            self._on_status("正在准备本地识别模型", "首次运行会自动下载小模型，请稍等。")
            model = create_whisper_model(self._settings)
            translator = create_text_translator(self._settings)
            self._on_status(
                "正在听取网页/系统音频",
                (
                    f"当前监听：{loopback_device.get('name', '默认扬声器')}。"
                    "播放英文网页视频即可出字幕。"
                ),
            )

            stream = audio_backend.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=frames_per_buffer,
            )

            while not self._stop_event.is_set():
                raw_audio = stream.read(frames_per_buffer, exception_on_overflow=False)
                if self._stop_event.is_set():
                    return

                audio = np.frombuffer(raw_audio, dtype=np.float32)
                if audio.size < channels:
                    continue
                audio = audio[: audio.size - (audio.size % channels)]
                audio = audio.reshape(-1, channels)

                if not _has_enough_volume(audio):
                    self._on_status("正在听取网页/系统音频", "未检测到明显人声，继续等待。")
                    continue

                mono_audio = _resample_to_16khz(_to_mono_float32(audio), sample_rate)
                source_text = self._transcribe(model, mono_audio)
                if not source_text.strip():
                    continue

                self._on_status("正在翻译", source_text.strip())
                translated_text = self._translate(translator, source_text)
                result = self._memory.upsert(source_text.strip(), translated_text.strip())
                if result is not None:
                    self._on_result(result)
        except Exception as exc:
            self._on_status("后台翻译已停止", str(exc))
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if audio_backend is not None:
                audio_backend.terminate()

    def _transcribe(self, model: object, audio: object) -> str:
        segments = transcribe_segments(model, audio, self._settings)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _translate(self, translator: object, source_text: str) -> str:
        cache_key = _normalize_for_compare(source_text)
        cached = self._translation_cache.get(cache_key)
        if cached is not None:
            return cached
        translated_text = translate_text(translator, source_text)
        polished = polish_chinese_translation(translated_text, source_text)
        self._translation_cache[cache_key] = polished
        if len(self._translation_cache) > 160:
            oldest_key = next(iter(self._translation_cache))
            self._translation_cache.pop(oldest_key, None)
        return polished


class RealtimeCorrectionMemory:
    def __init__(self) -> None:
        self._counter = 0
        self._current: BackgroundTranslation | None = None

    def upsert(self, source_text: str, translated_text: str) -> BackgroundTranslation | None:
        source_text = _clean_source_text(source_text)
        translated_text = polish_chinese_translation(translated_text, source_text)
        if not source_text or not translated_text:
            return None

        if self._current is None:
            return self._new_segment(source_text, translated_text)

        if _normalize_for_compare(source_text) == _normalize_for_compare(self._current.source_text):
            if translated_text == self._current.translated_text:
                return None
            return self._correct_current(source_text, translated_text)

        if _looks_like_correction(self._current.source_text, source_text):
            return self._correct_current(source_text, translated_text)

        return self._new_segment(source_text, translated_text)

    def _new_segment(self, source_text: str, translated_text: str) -> BackgroundTranslation:
        self._counter += 1
        self._current = BackgroundTranslation(
            segment_id=f"live-{self._counter:04d}",
            source_text=source_text,
            translated_text=translated_text,
            status="final",
            revision=1,
        )
        return self._current

    def _correct_current(self, source_text: str, translated_text: str) -> BackgroundTranslation:
        assert self._current is not None
        self._current = BackgroundTranslation(
            segment_id=self._current.segment_id,
            source_text=source_text,
            translated_text=translated_text,
            status="corrected",
            revision=self._current.revision + 1,
        )
        return self._current


def polish_chinese_translation(translated_text: str, source_text: str = "") -> str:
    text = translated_text.strip()
    if not text:
        return text

    replacements = (
        ("，并且", "，而且"),
        ("因此，", "所以，"),
        ("因此", "所以"),
        ("然而，", "不过，"),
        ("然而", "不过"),
        ("此外，", "另外，"),
        ("此外", "另外"),
        ("换句话说，", "也就是说，"),
        ("换句话说", "也就是说"),
        ("您可以", "可以"),
        ("你可以", "可以"),
        ("我们将会", "我们会"),
        ("我们将", "我们会"),
        ("这将会", "这会"),
        ("它将会", "它会"),
        ("是非常重要的", "很重要"),
        ("是很重要的", "很重要"),
        ("进行使用", "使用"),
        ("进行处理", "处理"),
        ("进行构建", "构建"),
        ("一个非常", "一个很"),
        ("非常地", "很"),
    )
    for source, target in replacements:
        text = text.replace(source, target)

    text = re.sub(r"\s+", "", text)
    text = (
        text.replace(",", "，")
        .replace(";", "；")
        .replace(":", "：")
        .replace("?", "？")
        .replace("!", "！")
    )
    text = re.sub(r"([，。！？；：])\1+", r"\1", text)
    if source_text.lower().strip().startswith(("so ", "so,", "therefore", "that's why")):
        text = re.sub(r"^(因此|所以)[，,]?", "所以，", text)
    if text and text[-1] not in "。！？…":
        text += "。"
    return text


def _clean_source_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned.strip(" \t\r\n,，")


def _normalize_for_compare(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text.lower())


def _looks_like_correction(previous: str, current: str) -> bool:
    previous_norm = _normalize_for_compare(previous)
    current_norm = _normalize_for_compare(current)
    if not previous_norm or not current_norm:
        return False
    if previous_norm in current_norm or current_norm in previous_norm:
        return True
    similarity = SequenceMatcher(None, previous_norm, current_norm).ratio()
    return similarity >= 0.58


def _has_enough_volume(audio: object) -> bool:
    import numpy as np

    rms = float(np.sqrt(np.mean(np.square(audio))))
    return rms > 0.01


def _to_mono_float32(audio: object) -> object:
    import numpy as np

    samples = np.asarray(audio)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    return np.asarray(samples, dtype=np.float32)


def _resample_to_16khz(audio: object, sample_rate: int) -> object:
    import numpy as np

    samples = np.asarray(audio, dtype=np.float32)
    if sample_rate == 16_000 or samples.size == 0:
        return samples

    duration = samples.size / sample_rate
    target_size = max(1, int(duration * 16_000))
    source_x = np.linspace(0, duration, num=samples.size, endpoint=False)
    target_x = np.linspace(0, duration, num=target_size, endpoint=False)
    return np.interp(target_x, source_x, samples).astype(np.float32)


class ThreadSafeResultSink:
    def __init__(self) -> None:
        self._queue: queue.Queue[BackgroundTranslation] = queue.Queue()

    def put(self, result: BackgroundTranslation) -> None:
        self._queue.put(result)

    def drain(self) -> list[BackgroundTranslation]:
        items: list[BackgroundTranslation] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                return items
