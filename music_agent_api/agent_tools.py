import requests
from langchain_core.tools import tool

API_BASE = "http://localhost:8001/api/v1"

@tool
def search_songs(q: str, limit: int = 20) -> dict:
    """
    当用户想听某首特定的歌、或者搜索某个歌手时调用此工具。
    输入参数：
    - q: 搜索关键词（如"七里香"、"周杰伦"）
    - limit: 返回结果数量（默认 20）
    """
    try:
        return requests.get(f"{API_BASE}/songs/search", params={"q": q, "limit": limit}).json()
    except Exception as e:
        return {"code": 5001, "msg": str(e)}

@tool
def get_play_url(song_id: str) -> dict:
    """
    当决定播放某首歌时，调用此工具获取音乐的真实播放流 URL。
    输入参数：
    - song_id: 歌曲的唯一 ID
    """
    try:
        return requests.get(f"{API_BASE}/songs/{song_id}/playurl").json()
    except Exception as e:
        return {"code": 5001, "msg": str(e)}

@tool
def recommend_scene(scene: str) -> dict:
    """
    当用户表达某种情绪或处于特定场景时，请求场景音乐推荐。
    输入参数：
    - scene: 必须是以下之一: late_night, work, workout, commute, relax, rainy
    """
    try:
        return requests.get(f"{API_BASE}/recommend/scene", params={"scene": scene, "limit": 10}).json()
    except Exception as e:
        return {"code": 5001, "msg": str(e)}

@tool
def report_playback(song_id: str, event: str, duration_ms: int, source: str = "ai_dj") -> dict:
    """
    当前端报告音乐播放结束时，调用此工具向云端打卡。
    输入参数：
    - song_id: 歌曲的唯一 ID
    - event: 必须是 "play_end"
    - duration_ms: 播放时长（毫秒）
    """
    try:
        import time
        payload = {
            "song_id": song_id, "event": event,
            "duration_ms": duration_ms, "ts": int(time.time() * 1000),
            "source": source
        }
        return requests.post(f"{API_BASE}/playback/report", json=payload).json()
    except Exception as e:
        return {"code": 5001, "msg": str(e)}