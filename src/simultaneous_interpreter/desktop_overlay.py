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

LAUNCHER_SIZE = 72
LAUNCHER_CENTER = LAUNCHER_SIZE // 2
TRANSPARENT_COLOR = "#ff00ff"
CAPTION_STATUS_FONT = ("Microsoft YaHei UI", 11, "bold")
CAPTION_SOURCE_FONT = ("Segoe UI", 13)
CAPTION_TRANSLATION_FONT = ("Microsoft YaHei UI", 32, "bold")


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
        self._caption_drag_start = (0, 0)
        self._caption_position_path = Path.cwd() / "caption-position.json"
        self._caption_position = _load_position(self._caption_position_path)
        self._translator: SystemAudioTranslator | None = None
        self._last_trail_at = 0.0
        self._trail_index = 0
        self._caption_status_text = "同传已开启"
        self._caption_source_text = ""
        self._caption_translation_text = ""

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
        self.bubble = self.canvas.create_oval(
            4,
            4,
            LAUNCHER_SIZE - 4,
            LAUNCHER_SIZE - 4,
            fill="",
            outline="#79d7ff",
            width=2,
            tags=("launcher",),
        )
        self._launcher_image = _load_photo_image(tk, "app-icon-72.png")
        if self._launcher_image is not None:
            self.canvas.create_image(
                LAUNCHER_CENTER,
                LAUNCHER_CENTER,
                image=self._launcher_image,
                tags=("launcher",),
            )
        else:
            self.canvas.create_text(
                LAUNCHER_CENTER,
                LAUNCHER_CENTER - 1,
                text="译",
                fill="#ffffff",
                font=("Microsoft YaHei UI", 22, "bold"),
                tags=("launcher",),
            )
        self.status_dot = self.canvas.create_oval(
            LAUNCHER_SIZE - 20,
            10,
            LAUNCHER_SIZE - 9,
            21,
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
        self.caption.attributes("-alpha", 0.98)
        self.caption.configure(bg=TRANSPARENT_COLOR)
        _set_transparent_color(self.caption)
        _set_window_icon(self.caption)
        self.caption_canvas = tk.Canvas(
            self.caption,
            width=self._caption_width(),
            height=self._caption_height(),
            highlightthickness=0,
            bg=TRANSPARENT_COLOR,
        )
        self.caption_canvas.pack(fill="both", expand=True)
        self._caption_items: list[int] = []

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

        for widget in (self.caption, self.caption_canvas):
            widget.bind("<ButtonPress-1>", self._begin_caption_drag)
            widget.bind("<B1-Motion>", self._drag_caption)
            widget.bind("<ButtonRelease-1>", self._end_caption_drag)

        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._place_caption()
        self._render_caption()

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
            self.canvas.itemconfigure(self.bubble, fill="", outline="#fb923c")
            self.canvas.itemconfigure(self.status_dot, fill="#f97316")
            self._set_caption_text(
                status=readiness.title,
                source=readiness.detail,
                translation="未启动真实网页音频翻译",
            )
            return

        self._active = True
        self.canvas.itemconfigure(self.bubble, fill="", outline="#49f2a8")
        self.canvas.itemconfigure(self.status_dot, fill="#18c47f")
        self._set_caption_text(status=readiness.title)
        self.caption.deiconify()
        self._place_caption()
        self._set_caption_text(source=readiness.detail, translation="正在等待网页音频")
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
        self.canvas.itemconfigure(self.bubble, fill="", outline="#79d7ff")
        self.canvas.itemconfigure(self.status_dot, fill="#9ca3af")
        self.caption.withdraw()

    def close(self) -> None:
        self._active = False
        if self._translator is not None:
            self._translator.stop()
            self._translator = None
        if self._launcher_poll_job is not None:
            try:
                self.root.after_cancel(self._launcher_poll_job)
            except Exception:
                pass
            self._launcher_poll_job = None
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
        self._set_caption_text(
            status=status_text,
            source=result.source_text,
            translation=result.translated_text,
        )
        self._place_caption()

    def _show_status(self, title: str, detail: str) -> None:
        translation = self._caption_translation_text or "等待字幕"
        self._set_caption_text(status=title, source=detail, translation=translation)

    def _set_caption_text(
        self,
        *,
        status: str | None = None,
        source: str | None = None,
        translation: str | None = None,
    ) -> None:
        if status is not None:
            self._caption_status_text = status
        if source is not None:
            self._caption_source_text = source
        if translation is not None:
            self._caption_translation_text = translation
        self._render_caption()

    def _render_caption(self) -> None:
        width = self._caption_width()
        height = self._caption_height()
        self.caption_canvas.configure(width=width, height=height)
        for item in self._caption_items:
            self.caption_canvas.delete(item)
        self._caption_items.clear()

        text_width = max(320, width - 48)
        self._caption_items.extend(
            _create_outlined_text(
                self.caption_canvas,
                x=24,
                y=18,
                text=self._caption_status_text,
                font=CAPTION_STATUS_FONT,
                fill="#8bd4ff",
                outline="#06111f",
                width=text_width,
            )
        )
        if self._caption_source_text:
            self._caption_items.extend(
                _create_outlined_text(
                    self.caption_canvas,
                    x=24,
                    y=48,
                    text=self._caption_source_text,
                    font=CAPTION_SOURCE_FONT,
                    fill="#e6eef8",
                    outline="#06111f",
                    width=text_width,
                    outline_width=1,
                )
            )
        self._caption_items.extend(
            _create_outlined_text(
                self.caption_canvas,
                x=24,
                y=84,
                text=self._caption_translation_text,
                font=CAPTION_TRANSLATION_FONT,
                fill="#ffffff",
                outline="#050b16",
                width=text_width,
                outline_width=3,
            )
        )

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
        self._caption_dragged = False
        self._caption_drag_start = (event.x_root, event.y_root)

    def _drag_caption(self, event: Any) -> None:
        start_x, start_y = self._caption_drag_start
        dx = event.x_root - start_x
        dy = event.y_root - start_y
        if abs(dx) + abs(dy) > 3:
            self._caption_dragged = True
        width = self._caption_width()
        height = self._caption_height()
        x = self.caption.winfo_x() + dx
        y = self.caption.winfo_y() + dy
        x, y = self._clamp_caption_position(x, y, width, height)
        self._caption_position = (x, y)
        self.caption.geometry(f"{width}x{height}+{x}+{y}")
        self._caption_drag_start = (event.x_root, event.y_root)

    def _end_caption_drag(self, _event: Any) -> None:
        if self._caption_dragged and self._caption_position is not None:
            _save_position(self._caption_position_path, self._caption_position)

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
                canvas.create_oval(
                    7,
                    7,
                    LAUNCHER_SIZE - 7,
                    LAUNCHER_SIZE - 7,
                    fill="",
                    outline="#8bd4ff",
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
        return min(1180, max(620, self.root.winfo_screenwidth() - 160))

    def _caption_height(self) -> int:
        return 188

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
        self.caption_canvas.configure(width=width, height=height)
        self.caption.geometry(f"{width}x{height}+{x}+{y}")

    def _clamp_caption_position(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        max_x = max(0, self.root.winfo_screenwidth() - width)
        max_y = max(0, self.root.winfo_screenheight() - height)
        return min(max(0, x), max_x), min(max(0, y), max_y)

    def _clamp_launcher_position(self, x: int, y: int) -> tuple[int, int]:
        max_x = max(0, self.root.winfo_screenwidth() - LAUNCHER_SIZE)
        max_y = max(0, self.root.winfo_screenheight() - LAUNCHER_SIZE)
        return min(max(0, x), max_x), min(max(0, y), max_y)


def _load_caption_position(path: Path) -> tuple[int, int] | None:
    return _load_position(path)


def _save_caption_position(path: Path, position: tuple[int, int]) -> None:
    _save_position(path, position)


def _create_outlined_text(
    canvas: Any,
    *,
    x: int,
    y: int,
    text: str,
    font: tuple[str, int] | tuple[str, int, str],
    fill: str,
    outline: str,
    width: int,
    outline_width: int = 2,
) -> list[int]:
    if not text:
        return []
    items: list[int] = []
    offsets = {
        (dx, dy)
        for dx in range(-outline_width, outline_width + 1)
        for dy in range(-outline_width, outline_width + 1)
        if dx or dy
    }
    for dx, dy in offsets:
        items.append(
            canvas.create_text(
                x + dx,
                y + dy,
                text=text,
                anchor="nw",
                justify="left",
                width=width,
                font=font,
                fill=outline,
            )
        )
    items.append(
        canvas.create_text(
            x,
            y,
            text=text,
            anchor="nw",
            justify="left",
            width=width,
            font=font,
            fill=fill,
        )
    )
    return items


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
    else:
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
