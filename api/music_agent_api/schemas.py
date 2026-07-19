from pydantic import BaseModel
from typing import List, Optional

class Artist(BaseModel):
    id: str
    name: str

class Album(BaseModel):
    id: str
    name: str
    cover_url: Optional[str] = None

class Song(BaseModel):
    id: str
    name: str
    artists: List[Artist]
    album: Album
    duration_ms: int
    fee: int
    cover_url: Optional[str] = None
    lyric_url: Optional[str] = None

class PlayUrlResponse(BaseModel):
    url: str
    expires_at: int
    br: int
    source: str
    song: Song

# --- 新增的 POST 请求体模型 ---

class PlaybackReportRequest(BaseModel):
    song_id: str
    event: str
    duration_ms: int
    ts: int
    source: str


class PhoneLoginRequest(BaseModel):
    phone: str
    password: str


class QrCheckRequest(BaseModel):
    key: str