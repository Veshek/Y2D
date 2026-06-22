"""Request/response schemas."""
from enum import Enum
from pydantic import BaseModel, Field


class Privacy(str, Enum):
    private = "private"
    unlisted = "unlisted"
    public = "public"


class TransferItem(BaseModel):
    file_id: str
    title: str | None = None  # defaults to the Drive filename if omitted
    privacy: Privacy = Privacy.private


class CreateTransfersRequest(BaseModel):
    items: list[TransferItem] = Field(min_length=1)


class TransferRecord(BaseModel):
    id: str
    file_id: str
    title: str
    privacy: Privacy
    status: str  # queued | downloading | uploading | done | error
    progress: int = 0  # 0-100
    youtube_video_id: str | None = None
    error: str | None = None
