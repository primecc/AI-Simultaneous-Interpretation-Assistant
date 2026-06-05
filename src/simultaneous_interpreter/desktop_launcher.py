import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

HOST = "127.0.0.1"
PORT = 8000
APP_URL = f"http://{HOST}:{PORT}"
LOG_PATH: Path | None = None
SERVER_ERROR: str | None = None
_DEVNULL_STREAMS = []


def main() -> None:
    _ensure_standard_streams()
    try:
        _main()
    except Exception as exc:
        _write_log(traceback.format_exc())
        if os.environ.get("AI_SI_HEADLESS") != "1":
            _show_error(str(exc))
        raise


def _main() -> None:
    runtime_dir = _runtime_dir()
    os.chdir(runtime_dir)
    global LOG_PATH
    LOG_PATH = runtime_dir / "launcher.log"
    _write_log("launcher starting")

    upload_dir = runtime_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("AI_SI_UPLOAD_DIR", str(upload_dir))

    if not _is_server_ready(PORT):
        if _is_port_busy(PORT):
            raise RuntimeError(f"端口 {PORT} 已被其他程序占用，请关闭占用程序后重新启动。")
        _start_server_thread()
        _wait_until_ready()
    _write_log("server ready")

    if os.environ.get("AI_SI_HEADLESS") == "1":
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return

    from simultaneous_interpreter.desktop_overlay import DesktopOverlayApp

    DesktopOverlayApp(app_url=APP_URL).run()


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def _start_server_thread() -> None:
    global SERVER_ERROR
    SERVER_ERROR = None
    thread = threading.Thread(target=_run_server, name="ai-si-server", daemon=True)
    thread.start()


def _run_server() -> None:
    global SERVER_ERROR
    try:
        from simultaneous_interpreter.main import app

        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="warning",
            log_config=None,
            access_log=False,
        )
        uvicorn.Server(config).run()
    except Exception:
        SERVER_ERROR = traceback.format_exc()
        _write_log(SERVER_ERROR)
        raise


def _wait_until_ready(timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if SERVER_ERROR is not None:
            raise RuntimeError(f"本地服务启动失败：{_last_error_line(SERVER_ERROR)}")
        if _is_server_ready(PORT):
            return
        time.sleep(0.25)
    raise RuntimeError("本地服务启动超时，请稍后重试。")


def _is_server_ready(port: int) -> bool:
    try:
        with urlopen(f"http://{HOST}:{port}/api/health", timeout=1.0) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def _is_port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, port)) == 0


def _write_log(message: str) -> None:
    if LOG_PATH is None:
        return
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def _ensure_standard_streams() -> None:
    stream_modes = {
        "stdin": "r",
        "stdout": "w",
        "stderr": "w",
    }
    for stream_name, mode in stream_modes.items():
        if getattr(sys, stream_name, None) is None:
            stream = open(os.devnull, mode, encoding="utf-8")
            _DEVNULL_STREAMS.append(stream)
            setattr(sys, stream_name, stream)


def _last_error_line(traceback_text: str) -> str:
    for line in reversed(traceback_text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return "未知错误，请查看 launcher.log"


def _show_error(message: str) -> None:
    try:
        import tkinter.messagebox as messagebox

        messagebox.showerror("AI 同声传译助手启动失败", message)
    except Exception:
        return


if __name__ == "__main__":
    main()
