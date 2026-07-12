from pydantic import BaseModel, Field
from typing import Optional, List


class Artist(BaseModel):
    id: str
    name: str


class Album(BaseModel):
    id: str
    name: str


class Song(BaseModel):
    id: str
    name: str
    artists: List[Artist]
    album: Album
    duration_ms: int
    cover_url: Optional[str] = None


class Playlist(BaseModel):
    playlist_id: str
    name: str
    source_url: str
    song_count: int
    created_at: int
    songs: List[Song] = []


class UserProfits(BaseModel):
    nickname: str = "用户"
    avatar_url: Optional[str] = None
    favorite_genres: List[str] = []
    favorite_artists: List[str] = []
    music_preference_desc: str = ""
    AI_conclustion: str = ""
    update_at: int = 0


class Settings(BaseModel):
    llm_apikey: str = ""
    netease_apikey: str = ""


class NeteaseLoginStatus(BaseModel):
    login_status: bool = False
    nickname: str = ""


class PlayerState(BaseModel):
    current_song: Optional[Song] = None
    play_url: Optional[str] = None
    is_playing: bool = False
    playlist: List[Song] = []
    current_index: int = 0


class ImportPlaylistRequest(BaseModel):
    playlist_url: str = Field(..., description="网易云歌单分享链接")


class UpdatePlaylistRequest(BaseModel):
    name: Optional[str] = None
    remark: Optional[str] = None


class UpdateUserBaseInfoRequest(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


class NeteaseLoginRequest(BaseModel):
    credential: str = Field(..., description="登录凭证（验证码/扫码临时token）")