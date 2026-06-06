from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SubtitleStatus(StrEnum):
    partial = "partial"
    final = "final"
    corrected = "corrected"


class SubtitleSegment(BaseModel):
    segment_id: str
    source_text: str
    translated_text: str
    status: SubtitleStatus = SubtitleStatus.partial
    revision: int = 1
    start_ms: int = 0
    end_ms: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SubtitleUpdate(BaseModel):
    event: str = "subtitle.upsert"
    segment: SubtitleSegment


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class MediaAsset(BaseModel):
    media_id: str
    filename: str
    content_type: str
    size_bytes: int
    url: str
