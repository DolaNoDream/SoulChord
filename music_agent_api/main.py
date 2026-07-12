import os
import time
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from auth_manager import auth_manager
from schemas import Song, Artist, Album, PlaybackReportRequest

app = FastAPI(title="Music & Feishu Agent API Service")

# ================= 环境变量配置 =================
NODEJS_API_BASE_URL = os.getenv("NETEASE_API_URL", "http://localhost:3000")

# 飞书应用配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_your_feishu_app_id")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "your_feishu_app_secret")
FEISHU_BASE_URL = "https://open.feishu.cn"

# 回调地址必须在飞书开发者后台配置完全一致
FEISHU_REDIRECT_URI = os.getenv("FEISHU_REDIRECT_URI", "http://localhost:8081/api/v1/feishu/auth/callback")

# MVP 阶段：内存全局缓存用户的 user_access_token
FEISHU_USER_TOKEN_CACHE = None


# ================= 辅助函数 =================

def get_direct_session():
    """
    【核心修复机制】
    创建一个纯净的 HTTP 会话：
    1. trust_env=False: 彻底无视宿主机/Docker的代理环境变量，强制直连，解决 SSL EOF。
    2. Connection: close: 禁用底层 TCP 复用，解决高频请求时的连接池断裂报错。
    """
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"Connection": "close"})
    return session


def parse_netease_song(item: dict) -> Song:
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


def get_feishu_tenant_access_token() -> str:
    """获取飞书应用的 tenant_access_token"""
    url = f"{FEISHU_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    # 使用纯净 Session
    res = get_direct_session().post(url, json=payload, timeout=10).json()

    if res.get("code") == 0:
        return res.get("tenant_access_token")
    else:
        raise Exception(f"获取飞书 Tenant Token 失败: {res.get('msg')}")


# ================= 1. 基础与状态接口 =================

@app.get("/api/v1/health")
async def health_check():
    try:
        requests.get(f"{NODEJS_API_BASE_URL}/", timeout=2)
        netease_ok = True
    except:
        netease_ok = False

    return {
        "code": 0, "msg": "ok",
        "data": {
            "status": "ok" if netease_ok else "error",
            "netease": {"available": netease_ok, "qps_left": 999},
            "xfyun": {"available": False}
        }
    }


@app.get("/api/v1/device/info")
async def get_device_info():
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
            "feishu_user_logged_in": FEISHU_USER_TOKEN_CACHE is not None
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

        return {"code": 0, "msg": "ok",
                "data": {"url": play_url, "expires_at": int(time.time() * 1000) + 86400000, "br": br, "source": source,
                         "song": song_info}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/songs/{id}/lyric")
async def get_song_lyric(id: str):
    try:
        payload = {"id": id}
        payload.update(auth_manager.get_request_params())
        res = requests.get(f"{NODEJS_API_BASE_URL}/lyric", params=payload, timeout=10).json()
        return {"code": 0, "msg": "ok", "data": {"lyric": res.get("lrc", {}).get("lyric", "")}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


# ================= 3. 推荐体系接口 =================

@app.get("/api/v1/recommend/fm")
async def recommend_fm(count: int = 3):
    try:
        payload = auth_manager.get_request_params()
        res = requests.get(f"{NODEJS_API_BASE_URL}/personal_fm", params=payload, timeout=10).json()
        songs = [parse_netease_song(song) for song in res.get("data", [])[:count]]
        return {"code": 0, "msg": "ok", "data": {"songs": [s.dict() for s in songs]}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/recommend/scene")
async def recommend_scene(scene: str, limit: int = 10):
    try:
        scene_map = {"late_night": "深夜", "work": "工作学习", "workout": "运动", "commute": "通勤", "relax": "放松",
                     "rainy": "下雨"}
        payload = {"keywords": scene_map.get(scene, "纯音乐"), "limit": limit, "type": 1}
        payload.update(auth_manager.get_request_params())
        res = requests.get(f"{NODEJS_API_BASE_URL}/cloudsearch", params=payload, timeout=10).json()
        songs = [parse_netease_song(song) for song in res.get("result", {}).get("songs", [])]
        return {"code": 0, "msg": "ok", "data": {"songs": [s.dict() for s in songs]}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/recommend/daily")
async def recommend_daily():
    try:
        payload = auth_manager.get_request_params()
        res = requests.get(f"{NODEJS_API_BASE_URL}/recommend/songs", params=payload, timeout=10).json()
        songs = [parse_netease_song(song) for song in res.get("data", {}).get("dailySongs", [])]
        return {"code": 0, "msg": "ok", "data": {"songs": [s.dict() for s in songs]}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.get("/api/v1/recommend/tags")
async def get_recommend_tags():
    tags = [
        {"key": "late_night", "name": "深夜", "icon": "🌙"},
        {"key": "work", "name": "工作", "icon": "💻"},
        {"key": "workout", "name": "运动", "icon": "🏃"},
        {"key": "commute", "name": "通勤", "icon": "🚌"},
        {"key": "relax", "name": "放松", "icon": "☕"},
        {"key": "rainy", "name": "下雨", "icon": "🌧️"}
    ]
    return {"code": 0, "msg": "ok", "data": {"tags": tags}}


# ================= 4. 用户数据接口 =================

@app.get("/api/v1/user/favorite_songs")
async def get_favorite_songs():
    try:
        status_res = requests.get(f"{NODEJS_API_BASE_URL}/login/status", params=auth_manager.get_request_params(),
                                  timeout=10).json()
        profile = status_res.get("data", {}).get("profile")
        if not profile:
            return {"code": 0, "msg": "ok", "data": {"songs": [], "user_logged_in": False}}

        likelist_res = requests.get(f"{NODEJS_API_BASE_URL}/likelist",
                                    params={"uid": profile.get("userId"), **auth_manager.get_request_params()},
                                    timeout=10).json()
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
    try:
        payload = {"id": id, "like": "true", **auth_manager.get_request_params()}
        requests.get(f"{NODEJS_API_BASE_URL}/like", params=payload, timeout=10)
        return {"code": 0, "msg": "ok", "data": {}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.delete("/api/v1/user/favorite_songs/{id}")
async def unlike_song(id: str):
    try:
        payload = {"id": id, "like": "false", **auth_manager.get_request_params()}
        requests.get(f"{NODEJS_API_BASE_URL}/like", params=payload, timeout=10)
        return {"code": 0, "msg": "ok", "data": {}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


@app.post("/api/v1/playback/report")
async def report_playback(req: PlaybackReportRequest):
    try:
        payload = {"id": req.song_id, "sourceid": req.source, "time": req.duration_ms // 1000,
                   **auth_manager.get_request_params()}
        requests.get(f"{NODEJS_API_BASE_URL}/scrobble", params=payload, timeout=10)
        return {"code": 0, "msg": "ok", "data": {}}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}


# ================= 5. 飞书 OAuth 2.0 用户授权与日程接口 =================

@app.get("/api/v1/feishu/auth/url")
async def get_feishu_auth_url():
    auth_url = f"https://open.feishu.cn/open-apis/authen/v1/index?redirect_uri={FEISHU_REDIRECT_URI}&app_id={FEISHU_APP_ID}"
    return {"code": 0, "msg": "ok", "data": {"auth_url": auth_url}}


@app.get("/api/v1/feishu/auth/callback", response_class=HTMLResponse)
async def feishu_auth_callback(code: str):
    global FEISHU_USER_TOKEN_CACHE
    try:
        tenant_token = get_feishu_tenant_access_token()

        url = f"{FEISHU_BASE_URL}/open-apis/authen/v1/access_token"
        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "grant_type": "authorization_code",
            "code": code
        }

        # 使用纯净 Session
        res = get_direct_session().post(url, headers=headers, json=payload, timeout=10).json()

        if res.get("code") == 0:
            FEISHU_USER_TOKEN_CACHE = res.get("data").get("access_token")
            return """
            <html>
                <body style="text-align:center; padding-top: 50px; font-family: sans-serif;">
                    <h2 style="color: green;">🎉 飞书日历授权成功！</h2>
                    <p>你的身份已绑定，现在 Agent 可以读取你的日程了。</p>
                    <p style="color: gray; font-size: 14px;">(你可以直接关闭此网页，返回到 Agent 对话界面)</p>
                </body>
            </html>
            """
        else:
            return f"<h1>授权失败</h1><p>{res.get('msg')}</p>"
    except Exception as e:
        return f"<h1>系统异常</h1><p>{str(e)}</p>"


@app.get("/api/v1/feishu/calendar/primary/events")
async def get_user_primary_events(start_time: str = None, end_time: str = None):
    global FEISHU_USER_TOKEN_CACHE

    if not FEISHU_USER_TOKEN_CACHE:
        return {"code": 401, "msg": "未授权：请先引导用户请求 /api/v1/feishu/auth/url 进行扫码登录", "data": {}}

    try:
        url = f"{FEISHU_BASE_URL}/open-apis/calendar/v4/calendars/primary/events"
        headers = {
            "Authorization": f"Bearer {FEISHU_USER_TOKEN_CACHE}"
        }
        params = {}
        if start_time: params["start_time"] = start_time
        if end_time: params["end_time"] = end_time

        # 使用纯净 Session
        res = get_direct_session().get(url, headers=headers, params=params, timeout=10).json()

        if res.get("code") != 0:
            return {"code": res.get("code"), "msg": f"飞书日程获取失败: {res.get('msg')}", "data": {}}

        return {"code": 0, "msg": "ok", "data": res.get("data")}
    except Exception as e:
        return {"code": 5001, "msg": str(e), "data": {}}