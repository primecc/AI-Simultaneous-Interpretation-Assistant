import json
from pathlib import Path

EXTENSION_DIR = Path("browser-extension")


def test_browser_extension_manifest_declares_content_script() -> None:
    manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 3
    assert manifest["content_scripts"][0]["matches"] == ["<all_urls>"]
    assert "content.js" in manifest["content_scripts"][0]["js"]


def test_browser_extension_content_script_contains_overlay_controls() -> None:
    content = (EXTENSION_DIR / "content.js").read_text(encoding="utf-8")

    assert "AI 同声传译" in content
    assert "ws://127.0.0.1:8000/ws/interpret" in content
    assert "开启" in content
    assert "关闭" in content
