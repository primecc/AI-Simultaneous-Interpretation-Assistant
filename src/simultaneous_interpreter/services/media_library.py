from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from simultaneous_interpreter.models import MediaAsset

ALLOWED_MEDIA_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
}


class MediaLibrary:
    def __init__(self, upload_dir: Path) -> None:
        self._upload_dir = upload_dir
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def list_assets(self) -> list[MediaAsset]:
        assets: list[MediaAsset] = []
        for path in sorted(self._upload_dir.iterdir(), key=lambda item: item.stat().st_mtime):
            if path.is_file() and path.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS:
                assets.append(self._asset_from_path(path))
        return assets

    async def save_upload(self, upload: UploadFile) -> MediaAsset:
        original_name = Path(upload.filename or "media").name
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_MEDIA_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_MEDIA_EXTENSIONS))
            raise ValueError(f"Unsupported media type. Allowed extensions: {allowed}")

        media_id = uuid4().hex
        stored_name = f"{media_id}{extension}"
        target = self._upload_dir / stored_name
        content = await upload.read()
        target.write_bytes(content)
        return self._asset_from_path(target, content_type=upload.content_type)

    def find(self, media_id: str) -> MediaAsset | None:
        for asset in self.list_assets():
            if asset.media_id == media_id:
                return asset
        return None

    def _asset_from_path(self, path: Path, content_type: str | None = None) -> MediaAsset:
        return MediaAsset(
            media_id=path.stem,
            filename=path.name,
            content_type=content_type or _guess_content_type(path),
            size_bytes=path.stat().st_size,
            url=f"/media/{path.name}",
        )


def _guess_content_type(path: Path) -> str:
    if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"}:
        return "audio/*"
    return "video/*"
