import time
import requests
import os
from fastapi import FastAPI
from auth_manager import auth_manager
from schemas import Song, Artist, Album, PlaybackReportRequest

app = FastAPI(title="Music API Service")
NODEJS_API_BASE_URL = os.getenv("NETEASE_API_URL", "http://localhost:3000")


def parse_netease_song(item: dict) -> Song:
    """将网易云原生歌曲结构清洗转换为契约结构"""
    # 兼容两种网易云数据格式（搜索/详情接口使用 ar/al，漫游/推荐接口有时使用 artists/album）
    artists_data = item.get("ar") or item.get("artists") or []
    album_data = item.get("al") or item.get("album") or {}

    return Song(
        id=str(item.get("id")),
        name=item.get("name"),
        artists=[Artist(id=str(ar.get("id")), name=ar.get("name")) for ar in artists_data],
        album=Album(
            id=str(album_data.get("id")),
            name=album_data.get("name"),
            cover_url=album_data.get("picUrl")
        ),
        duration_ms=item.get("dt") or item.get("duration") or 0,
        fee=item.get("fee", 0),
        cover_url=album_data.get("picUrl")
    )


# ================= 1. 基础与状态接口 =================

@app.get("/api/v1/health")
async def health_check():
    """健康检查（Agent 启动时调一次）"""
    try:
        requests.get(f"{NODEJS_API_BASE_URL}/", timeout=2)
        netease_ok = True
    except:
        netease_ok = False

    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "status": "ok" if netease_ok else "error",
            "netease": {"available": netease_ok, "qps_left": 999},
            "xfyun": {"available": False}
        }
    }


@app.get("/api/v1/device/info")
async def get_device_info():
    """当前 deviceid 和 token 信息（调试用）"""
    anonymous_token = "not_found"
    if "MUSIC_A_T=" in auth_manager.cookie_str:
        parts = auth_manager.cookie_str.split("MUSIC_A_T=")
        if len(parts) > 1:
            anonymous_token = parts[1].split(";")[0]

    return {
        "code": 0, "msg": "ok",
        "data": {
            "device_id": auth_manager.device_id,
            "anonymous_token": anonymous_token,
            "token_expires": -1,
            "netease_logged_in": False
        }
    }


# ================= 2. 歌曲能力接口 =================

@app.get("/api/v1/songs/search")
async def search_songs(q: str, limit: int = 20):
    payload = {"keywords": q, "limit": limit}
    payload.update(auth_manager.get_request_params())
    try:
        res = requests.get(f"{NODEJS_API_BASE_URL}/cloudsearch", params=payload, timeout=10).json()
        if res.get("code") != 200:
            return {"code": 4101, "msg": "网易云官方接口失败", "data": {}}

        songs_data = res.get("result", {}).get("songs", [])
        songs = [parse_netease_song(song) for song in songs_data]
        return {
            "code": 0, "msg": "ok",
            "data": {
                "total": res.get("result", {}).get("songCount", 0),
                "songs": [song.dict() for song in songs]
            }
        }
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/songs/{id}")
async def get_song_detail(id: str):
    payload = {"ids": id}
    payload.update(auth_manager.get_request_params())
    try:
        res = requests.get(f"{NODEJS_API_BASE_URL}/song/detail", params=payload, timeout=10).json()

        if res.get("code") != 200 or not res.get("songs"):
            return {"code": 4003, "msg": "资源不存在", "data": {}}

        song = parse_netease_song(res["songs"][0])
        song.lyric_url = f"http://localhost:8001/api/v1/songs/{id}/lyric"
        return {"code": 0, "msg": "ok", "data": {"song": song.dict()}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/songs/{id}/playurl")
async def get_play_url(id: str, br: int = 128000):
    try:
        detail_res = await get_song_detail(id)
        if detail_res["code"] != 0: return detail_res
        song_info = detail_res["data"]["song"]

        payload = {"id": id, "level": "standard"}
        payload.update(auth_manager.get_request_params())
        url_res = requests.get(f"{NODEJS_API_BASE_URL}/song/url/v1", params=payload, timeout=10).json()

        play_url = None
        source = "official"
        if url_res.get("code") == 200 and url_res.get("data"):
            play_url = url_res["data"][0].get("url")

        if not play_url:
            source = "outer_url"
            play_url = f"https://music.163.com/song/media/outer/url?id={id}.mp3"
            try:
                check_head = requests.head(play_url, allow_redirects=True, timeout=3)
                if check_head.status_code == 404 or "error" in check_head.url:
                    return {"code": 4103, "msg": "播放 URL 获取失败（已降级但仍失败）", "data": {}}
            except:
                return {"code": 4103, "msg": "播放 URL 获取失败", "data": {}}

        return {
            "code": 0, "msg": "ok",
            "data": {
                "url": play_url, "expires_at": int(time.time() * 1000) + 86400000,
                "br": br, "source": source, "song": song_info
            }
        }
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/songs/{id}/lyric")
async def get_song_lyric(id: str):
    """获取歌词（LRC 格式文本）"""
    try:
        payload = {"id": id}
        payload.update(auth_manager.get_request_params())
        res = requests.get(f"{NODEJS_API_BASE_URL}/lyric", params=payload, timeout=10).json()
        lyric_text = res.get("lrc", {}).get("lyric", "")
        return {"code": 0, "msg": "ok", "data": {"lyric": lyric_text}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


# ================= 3. 推荐体系接口 =================

@app.get("/api/v1/recommend/fm")
async def recommend_fm(count: int = 3):
    """网易云私人漫游"""
    try:
        payload = auth_manager.get_request_params()
        res = requests.get(f"{NODEJS_API_BASE_URL}/personal_fm", params=payload, timeout=10).json()
        songs_data = res.get("data", [])[:count]
        songs = [parse_netease_song(song) for song in songs_data]
        return {"code": 0, "msg": "ok", "data": {"songs": [s.dict() for s in songs]}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/recommend/scene")
async def recommend_scene(scene: str, limit: int = 10):
    """场景音乐推荐"""
    try:
        scene_map = {
            "late_night": "深夜", "work": "工作学习", "workout": "运动",
            "commute": "通勤", "relax": "放松", "rainy": "下雨"
        }
        keyword = scene_map.get(scene, "纯音乐")

        payload = {"keywords": keyword, "limit": limit, "type": 1}
        payload.update(auth_manager.get_request_params())
        res = requests.get(f"{NODEJS_API_BASE_URL}/cloudsearch", params=payload, timeout=10).json()

        songs_data = res.get("result", {}).get("songs", [])
        songs = [parse_netease_song(song) for song in songs_data]
        return {"code": 0, "msg": "ok", "data": {"songs": [s.dict() for s in songs]}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/recommend/daily")
async def recommend_daily():
    """每日推荐"""
    try:
        payload = auth_manager.get_request_params()
        res = requests.get(f"{NODEJS_API_BASE_URL}/recommend/songs", params=payload, timeout=10).json()

        songs_data = res.get("data", {}).get("dailySongs", [])
        songs = [parse_netease_song(song) for song in songs_data]
        return {"code": 0, "msg": "ok", "data": {"songs": [s.dict() for s in songs]}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/recommend/tags")
async def get_recommend_tags():
    """获取可用场景标签列表"""
    tags = [
        {"key": "late_night", "name": "深夜", "icon": "🌙"},
        {"key": "work", "name": "工作", "icon": "💻"},
        {"key": "workout", "name": "运动", "icon": "🏃"},
        {"key": "commute", "name": "通勤", "icon": "🚌"},
        {"key": "relax", "name": "放松", "icon": "☕"},
        {"key": "rainy", "name": "下雨", "icon": "🌧️"}
    ]
    return {"code": 0, "msg": "ok", "data": {"tags": tags}}


# ================= 4. 用户数据与打卡接口 =================

@app.get("/api/v1/user/favorite_songs")
async def get_favorite_songs():
    """获取用户红心歌曲"""
    try:
        status_res = requests.get(f"{NODEJS_API_BASE_URL}/login/status", params=auth_manager.get_request_params(),
                                  timeout=10).json()
        profile = status_res.get("data", {}).get("profile")

        if not profile:
            return {"code": 0, "msg": "ok", "data": {"songs": [], "user_logged_in": False}}

        uid = profile.get("userId")
        likelist_res = requests.get(f"{NODEJS_API_BASE_URL}/likelist",
                                    params={"uid": uid, **auth_manager.get_request_params()}, timeout=10).json()
        ids = likelist_res.get("ids", [])[:50]

        if not ids:
            return {"code": 0, "msg": "ok", "data": {"songs": [], "user_logged_in": True}}

        detail_res = requests.get(f"{NODEJS_API_BASE_URL}/song/detail",
                                  params={"ids": ",".join(map(str, ids)), **auth_manager.get_request_params()},
                                  timeout=10).json()
        songs = [parse_netease_song(song) for song in detail_res.get("songs", [])]

        return {"code": 0, "msg": "ok", "data": {"songs": [s.dict() for s in songs], "user_logged_in": True}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.post("/api/v1/user/favorite_songs/{id}")
async def like_song(id: str):
    """将歌曲加入红心"""
    try:
        payload = {"id": id, "like": "true"}
        payload.update(auth_manager.get_request_params())
        requests.get(f"{NODEJS_API_BASE_URL}/like", params=payload, timeout=10)
        return {"code": 0, "msg": "ok", "data": {}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.delete("/api/v1/user/favorite_songs/{id}")
async def unlike_song(id: str):
    """取消红心"""
    try:
        payload = {"id": id, "like": "false"}
        payload.update(auth_manager.get_request_params())
        requests.get(f"{NODEJS_API_BASE_URL}/like", params=payload, timeout=10)
        return {"code": 0, "msg": "ok", "data": {}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.post("/api/v1/playback/report")
async def report_playback(req: PlaybackReportRequest):
    """向网易云回传播放数据"""
    try:
        payload = {
            "id": req.song_id,
            "sourceid": req.source,
            "time": req.duration_ms // 1000
        }
        payload.update(auth_manager.get_request_params())
        requests.get(f"{NODEJS_API_BASE_URL}/scrobble", params=payload, timeout=10)
        return {"code": 0, "msg": "ok", "data": {}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}