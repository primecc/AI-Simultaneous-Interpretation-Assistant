import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

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
    source_text: str
    translated_text: str
    status: str = "final"


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
            chunk_seconds = 4
            frames_per_buffer = sample_rate * chunk_seconds

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
                self._on_result(
                    BackgroundTranslation(
                        source_text=source_text.strip(),
                        translated_text=translated_text.strip(),
                    )
                )
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
        return translate_text(translator, source_text)


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
