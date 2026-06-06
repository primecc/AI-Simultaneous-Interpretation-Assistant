import json
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any

from simultaneous_interpreter.config import get_settings
from simultaneous_interpreter.services.system_audio_translator import (
    BackgroundTranslation,
    SystemAudioTranslator,
)

LAUNCHER_SIZE = 96
LAUNCHER_CENTER = LAUNCHER_SIZE // 2
LAUNCHER_ICON_FILE = "app-icon-launcher-96.png"
TRANSPARENT_COLOR = "#ff00ff"
CAPTION_BG = "#0b1220"


class DesktopOverlayApp:
    def __init__(self, *, app_url: str) -> None:
        import tkinter as tk

        self._tk = tk
        self._app_url = app_url
        self._active = False
        self._dragged = False
        self._drag_start = (0, 0)
        self._launcher_dragging = False
        self._launcher_drag_offset = (0, 0)
        self._launcher_poll_job: str | None = None
        self._launcher_position_path = Path.cwd() / "launcher-position.json"
        self._launcher_position = _load_position(self._launcher_position_path)
        self._caption_dragged = False
        self._caption_dragging = False
        self._caption_drag_start = (0, 0)
        self._caption_drag_offset = (0, 0)
        self._caption_poll_job: str | None = None
        self._caption_position_path = Path.cwd() / "caption-position.json"
        self._caption_position = _load_position(self._caption_position_path)
        self._translator: SystemAudioTranslator | None = None
        self._last_trail_at = 0.0
        self._trail_index = 0

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.title("AI 同声传译助手")
        _set_window_icon(self.root)
        self.root.geometry(self._launcher_geometry())
        self.root.configure(bg=TRANSPARENT_COLOR)
        _set_transparent_color(self.root)

        self.canvas = tk.Canvas(
            self.root,
            width=LAUNCHER_SIZE,
            height=LAUNCHER_SIZE,
            highlightthickness=0,
            bg=TRANSPARENT_COLOR,
        )
        self.canvas.pack(fill="both", expand=True)
        self._launcher_image = _load_photo_image(tk, LAUNCHER_ICON_FILE)
        if self._launcher_image is not None:
            self.canvas.create_image(
                LAUNCHER_CENTER,
                LAUNCHER_CENTER,
                image=self._launcher_image,
                tags=("launcher",),
            )
        else:
            self.canvas.create_rectangle(
                6,
                6,
                LAUNCHER_SIZE - 6,
                LAUNCHER_SIZE - 6,
                fill="#103945",
                outline="#74e4ff",
                width=2,
                tags=("launcher",),
            )
            self.canvas.create_text(
                LAUNCHER_CENTER,
                LAUNCHER_CENTER - 1,
                text="译",
                fill="#ffffff",
                font=("Microsoft YaHei UI", 22, "bold"),
                tags=("launcher",),
            )
        self.status_dot = self.canvas.create_oval(
            LAUNCHER_SIZE - 25,
            13,
            LAUNCHER_SIZE - 11,
            27,
            fill="#9ca3af",
            outline="#ffffff",
            width=2,
            tags=("launcher",),
        )
        self._trail_windows = self._create_trail_windows()

        self.caption = tk.Toplevel(self.root)
        self.caption.withdraw()
        self.caption.overrideredirect(True)
        self.caption.attributes("-topmost", True)
        self.caption.attributes("-alpha", 0.9)
        self.caption.configure(bg=CAPTION_BG)
        _set_window_icon(self.caption)

        self.status_label = tk.Label(
            self.caption,
            text="同传已开启",
            bg=CAPTION_BG,
            fg="#8bd4ff",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.status_label.pack(anchor="w", padx=18, pady=(13, 2))
        self.source_label = tk.Label(
            self.caption,
            text="",
            bg=CAPTION_BG,
            fg="#b6c2d2",
            justify="left",
            font=("Segoe UI", 11),
        )
        self.source_label.pack(anchor="w", fill="x", padx=18)
        self.translation_label = tk.Label(
            self.caption,
            text="",
            bg=CAPTION_BG,
            fg="#ffffff",
            justify="left",
            font=("Microsoft YaHei UI", 24, "bold"),
        )
        self.translation_label.pack(anchor="w", fill="x", padx=18, pady=(4, 16))

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="开启/关闭字幕", command=self.toggle)
        self.menu.add_command(label="打开软件界面", command=lambda: webbrowser.open(self._app_url))
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.close)

        for widget in (self.root, self.canvas):
            widget.bind("<ButtonPress-1>", self._begin_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)
            widget.bind("<Button-3>", self._show_menu)
        self.canvas.tag_bind("launcher", "<ButtonPress-1>", self._begin_drag)
        self.canvas.tag_bind("launcher", "<B1-Motion>", self._drag)
        self.canvas.tag_bind("launcher", "<ButtonRelease-1>", self._end_drag)
        self.canvas.tag_bind("launcher", "<Button-3>", self._show_menu)

        for widget in (self.caption, self.status_label, self.source_label, self.translation_label):
            widget.bind("<ButtonPress-1>", self._begin_caption_drag)
            widget.bind("<B1-Motion>", self._drag_caption)
            widget.bind("<ButtonRelease-1>", self._end_caption_drag)

        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._place_caption()

    def run(self) -> None:
        self.root.mainloop()

    def toggle(self) -> None:
        if self._active:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        settings = get_settings()
        readiness = SystemAudioTranslator.check_readiness(settings)
        self.caption.deiconify()
        self._place_caption()

        if not readiness.ready:
            self._active = False
            self.canvas.itemconfigure(self.status_dot, fill="#f97316")
            self.status_label.configure(text=readiness.title)
            self.source_label.configure(
                text=readiness.detail,
                wraplength=self._caption_width() - 36,
            )
            self.translation_label.configure(
                text="未启动真实网页音频翻译",
                wraplength=self._caption_width() - 36,
            )
            return

        self._active = True
        self.canvas.itemconfigure(self.status_dot, fill="#18c47f")
        self.status_label.configure(text=readiness.title)
        self.caption.deiconify()
        self._place_caption()
        self.source_label.configure(text=readiness.detail, wraplength=self._caption_width() - 36)
        self.translation_label.configure(
            text="正在等待网页音频",
            wraplength=self._caption_width() - 36,
        )
        self._translator = SystemAudioTranslator(
            settings=settings,
            on_result=lambda result: self.root.after(0, self._show_translation, result),
            on_status=lambda title, detail: self.root.after(0, self._show_status, title, detail),
        )
        self._translator.start()

    def stop(self) -> None:
        self._active = False
        if self._translator is not None:
            self._translator.stop()
            self._translator = None
        self.canvas.itemconfigure(self.status_dot, fill="#9ca3af")
        self.caption.withdraw()

    def close(self) -> None:
        self._active = False
        if self._translator is not None:
            self._translator.stop()
            self._translator = None
        self._cancel_drag_jobs()
        try:
            self.caption.withdraw()
        except Exception:
            pass
        for window in self._trail_windows:
            try:
                window.withdraw()
                window.destroy()
            except Exception:
                pass
        try:
            self.caption.destroy()
        except Exception:
            pass
        try:
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def _show_translation(self, result: BackgroundTranslation) -> None:
        if not self._active:
            return
        status_text = "实时中文字幕"
        if result.status == "corrected":
            status_text = f"实时中文字幕 · 已自动修正第 {result.revision} 版"
        self.status_label.configure(text=status_text)
        self.source_label.configure(text=result.source_text, wraplength=self._caption_width() - 36)
        self.translation_label.configure(
            text=result.translated_text,
            wraplength=self._caption_width() - 36,
        )
        self._place_caption()

    def _show_status(self, title: str, detail: str) -> None:
        self.status_label.configure(text=title)
        self.source_label.configure(text=detail, wraplength=self._caption_width() - 36)
        if not self.translation_label.cget("text"):
            self.translation_label.configure(text="等待字幕")

    def _begin_drag(self, event: Any) -> None:
        if self._launcher_dragging and self._launcher_poll_job is not None:
            return
        self._dragged = False
        self._drag_start = (event.x_root, event.y_root)
        self._launcher_dragging = True
        self._launcher_drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )
        self._poll_launcher_drag()

    def _drag(self, event: Any) -> None:
        self._move_launcher_to_pointer(event.x_root, event.y_root)

    def _end_drag(self, _event: Any) -> None:
        self._finish_launcher_drag()

    def _poll_launcher_drag(self) -> None:
        if not self._launcher_dragging:
            return
        if not _is_left_button_down():
            self._finish_launcher_drag()
            return
        x_root, y_root = self.root.winfo_pointerxy()
        self._move_launcher_to_pointer(x_root, y_root)
        self._launcher_poll_job = self.root.after(16, self._poll_launcher_drag)

    def _move_launcher_to_pointer(self, x_root: int, y_root: int) -> None:
        start_x, start_y = self._drag_start
        if abs(x_root - start_x) + abs(y_root - start_y) > 3:
            self._dragged = True
        if not self._dragged:
            return
        self._show_drag_trail(self.root.winfo_x(), self.root.winfo_y())
        offset_x, offset_y = self._launcher_drag_offset
        x, y = self._clamp_launcher_position(x_root - offset_x, y_root - offset_y)
        self._launcher_position = (x, y)
        self.root.geometry(f"+{x}+{y}")

    def _finish_launcher_drag(self) -> None:
        if not self._launcher_dragging:
            return
        self._launcher_dragging = False
        if self._launcher_poll_job is not None:
            try:
                self.root.after_cancel(self._launcher_poll_job)
            except Exception:
                pass
            self._launcher_poll_job = None
        if not self._dragged:
            self.toggle()
            return
        if self._launcher_position is not None:
            _save_position(self._launcher_position_path, self._launcher_position)

    def _show_menu(self, event: Any) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _begin_caption_drag(self, event: Any) -> None:
        if self._caption_dragging and self._caption_poll_job is not None:
            return
        self._caption_dragged = False
        self._caption_drag_start = (event.x_root, event.y_root)
        self._caption_dragging = True
        self._caption_drag_offset = (
            event.x_root - self.caption.winfo_x(),
            event.y_root - self.caption.winfo_y(),
        )
        self._poll_caption_drag()

    def _drag_caption(self, event: Any) -> None:
        self._move_caption_to_pointer(event.x_root, event.y_root)

    def _end_caption_drag(self, _event: Any) -> None:
        self._finish_caption_drag()

    def _poll_caption_drag(self) -> None:
        if not self._caption_dragging:
            return
        if not _is_left_button_down():
            self._finish_caption_drag()
            return
        x_root, y_root = self.root.winfo_pointerxy()
        self._move_caption_to_pointer(x_root, y_root)
        self._caption_poll_job = self.root.after(16, self._poll_caption_drag)

    def _move_caption_to_pointer(self, x_root: int, y_root: int) -> None:
        start_x, start_y = self._caption_drag_start
        if abs(x_root - start_x) + abs(y_root - start_y) > 3:
            self._caption_dragged = True
        if not self._caption_dragged:
            return
        width = self._caption_width()
        height = self._caption_height()
        offset_x, offset_y = self._caption_drag_offset
        x, y = self._clamp_caption_position(x_root - offset_x, y_root - offset_y, width, height)
        self._caption_position = (x, y)
        self.caption.geometry(f"{width}x{height}+{x}+{y}")

    def _finish_caption_drag(self) -> None:
        if not self._caption_dragging:
            return
        self._caption_dragging = False
        if self._caption_poll_job is not None:
            try:
                self.root.after_cancel(self._caption_poll_job)
            except Exception:
                pass
            self._caption_poll_job = None
        if self._caption_dragged and self._caption_position is not None:
            _save_position(self._caption_position_path, self._caption_position)

    def _cancel_drag_jobs(self) -> None:
        if self._launcher_poll_job is not None:
            try:
                self.root.after_cancel(self._launcher_poll_job)
            except Exception:
                pass
            self._launcher_poll_job = None
        if self._caption_poll_job is not None:
            try:
                self.root.after_cancel(self._caption_poll_job)
            except Exception:
                pass
            self._caption_poll_job = None

    def _create_trail_windows(self) -> list[Any]:
        windows: list[Any] = []
        for alpha in (0.24, 0.18, 0.13, 0.09, 0.06):
            window = self._tk.Toplevel(self.root)
            window.withdraw()
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.attributes("-alpha", alpha)
            window.configure(bg=TRANSPARENT_COLOR)
            _make_click_through(window)
            canvas = self._tk.Canvas(
                window,
                width=LAUNCHER_SIZE,
                height=LAUNCHER_SIZE,
                highlightthickness=0,
                bg=TRANSPARENT_COLOR,
            )
            canvas.pack(fill="both", expand=True)
            _set_transparent_color(window)
            if self._launcher_image is not None:
                canvas.create_image(LAUNCHER_CENTER, LAUNCHER_CENTER, image=self._launcher_image)
            else:
                canvas.create_rectangle(
                    8,
                    8,
                    LAUNCHER_SIZE - 8,
                    LAUNCHER_SIZE - 8,
                    fill="#103945",
                    outline="#74e4ff",
                    width=2,
                )
                canvas.create_text(
                    LAUNCHER_CENTER,
                    LAUNCHER_CENTER - 1,
                    text="译",
                    fill="#ffffff",
                    font=("Microsoft YaHei UI", 22, "bold"),
                )
            windows.append(window)
        return windows

    def _show_drag_trail(self, x: int, y: int) -> None:
        now = time.monotonic()
        if now - self._last_trail_at < 0.028:
            return
        self._last_trail_at = now
        window = self._trail_windows[self._trail_index % len(self._trail_windows)]
        self._trail_index += 1
        window.geometry(f"{LAUNCHER_SIZE}x{LAUNCHER_SIZE}+{x}+{y}")
        window.deiconify()
        window.lift()
        self.root.after(180, window.withdraw)

    def _caption_width(self) -> int:
        return min(980, max(520, self.root.winfo_screenwidth() - 180))

    def _caption_height(self) -> int:
        return 156

    def _launcher_geometry(self) -> str:
        if self._launcher_position is None:
            x = self.root.winfo_screenwidth() - LAUNCHER_SIZE - 40
            y = 220
        else:
            x, y = self._clamp_launcher_position(
                self._launcher_position[0],
                self._launcher_position[1],
            )
        return f"{LAUNCHER_SIZE}x{LAUNCHER_SIZE}+{x}+{y}"

    def _place_caption(self) -> None:
        width = self._caption_width()
        height = self._caption_height()
        if self._caption_position is None:
            x = int((self.root.winfo_screenwidth() - width) / 2)
            y = self.root.winfo_screenheight() - height - 72
        else:
            x, y = self._clamp_caption_position(
                self._caption_position[0],
                self._caption_position[1],
                width,
                height,
            )
        self.caption.geometry(f"{width}x{height}+{x}+{y}")

    def _clamp_caption_position(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        max_x = max(0, self.root.winfo_screenwidth() - width)
        max_y = max(0, self.root.winfo_screenheight() - height)
        return min(max(0, x), max_x), min(max(0, y), max_y)

    def _clamp_launcher_position(self, x: int, y: int) -> tuple[int, int]:
        max_x = max(0, self.root.winfo_screenwidth() - LAUNCHER_SIZE)
        max_y = max(0, self.root.winfo_screenheight() - LAUNCHER_SIZE)
        return min(max(0, x), max_x), min(max(0, y), max_y)


def _load_position(path: Path) -> tuple[int, int] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    x = data.get("x")
    y = data.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return x, y
    return None


def _load_caption_position(path: Path) -> tuple[int, int] | None:
    return _load_position(path)


def _save_caption_position(path: Path, position: tuple[int, int]) -> None:
    _save_position(path, position)


def _save_position(path: Path, position: tuple[int, int]) -> None:
    try:
        path.write_text(
            json.dumps({"x": position[0], "y": position[1]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return


def _load_photo_image(tk_module: Any, filename: str) -> Any | None:
    path = _asset_path(filename)
    if not path.exists():
        return None
    try:
        return tk_module.PhotoImage(file=str(path))
    except Exception:
        return None


def _set_window_icon(window: Any) -> None:
    icon_path = _asset_path("app-icon.ico")
    if not icon_path.exists():
        return
    try:
        window.iconbitmap(default=str(icon_path))
    except Exception:
        return


def _set_transparent_color(window: Any) -> None:
    try:
        window.attributes("-transparentcolor", TRANSPARENT_COLOR)
    except Exception:
        return


def _asset_path(filename: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return base / "simultaneous_interpreter" / "assets" / filename
    base = Path(__file__).resolve().parent
    return base / "assets" / filename


def _is_left_button_down() -> bool:
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
    except Exception:
        return True


def _make_click_through(window: Any) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = window.winfo_id()
        get_window_long = ctypes.windll.user32.GetWindowLongW
        set_window_long = ctypes.windll.user32.SetWindowLongW
        style = get_window_long(hwnd, -20)
        set_window_long(hwnd, -20, style | 0x00000020 | 0x00080000)
    except Exception:
        return
