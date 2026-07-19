"""HTTP 路由注册 — 11 群组（health / init / settings / playlist / user / feedback / memory / history / netease / proxy / feishu）。

所有数据读写经 Store 层，不直接 open json。
"""

import time
from typing import Optional

import httpx
from fastapi import FastAPI, Body, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.state import memory_store, player_state, program_state, settings_store, playlist_store
from agent.shared.enums import InitMode
from agent.config import settings as config_settings


# ── 统一响应 ──

def ok(data: dict | list | None = None) -> dict:
    return {"code": 0, "msg": "ok", "data": data or {}}


def fail(code: int = 9999, msg: str = "服务内部异常") -> dict:
    return {"code": code, "msg": msg, "data": {}}


# ── 常量 ──

MUSIC_API_BASE = "http://localhost:8081"


# ── 请求模型 ──

class SettingsUpdate(BaseModel):
    llm_apikey: Optional[str] = None
    netease_apikey: Optional[str] = None


class UserBaseInfoUpdate(BaseModel):
    nickname: str = ""
    avatar_url: str = ""


class NeteaseLoginRequest(BaseModel):
    type: str = "phone"           # "phone" | "qr"
    phone: str = ""               # 手机号（phone 登录）
    password: str = ""            # 密码（phone 登录）
    token: str = ""               # QR token（qr 登录）


class PlaylistImportRequest(BaseModel):
    playlist_url: str


class PlaylistUpdateRequest(BaseModel):
    name: Optional[str] = None
    remark: Optional[str] = None


class QrCheckRequest(BaseModel):
    key: str


class FeedbackRequest(BaseModel):
    song_id: str
    action: str  # like / dislike / skip / favorite
    ts: int = 0


class MemoryUpdateRequest(BaseModel):
    key: str
    category: str  # profile / preference / context / feedback
    value: object
    source: str = "user_input"


# ── 辅助 ──

async def _call_music_api(method: str, path: str, json_data: dict | None = None) -> dict | None:
    """调 music_agent_api，失败返回 None。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{MUSIC_API_BASE}{path}"
            if method == "GET":
                resp = await client.get(url, params=json_data)
            else:
                resp = await client.post(url, json=json_data)
            if resp.status_code == 200:
                body = resp.json()
                return body
    except Exception:
        pass
    return None


async def _get_netease_login_status() -> dict:
    """从 music_agent_api 查询网易云登录状态，失败返回离线状态。"""
    result = await _call_music_api("GET", "/api/v1/login/status")
    if result and result.get("code") == 0:
        data = result.get("data", {})
        return {"login_status": data.get("logged_in", False), "nickname": data.get("nickname", "")}
    return {"login_status": False, "nickname": ""}

def _unwrap_memory_profile(raw: dict) -> dict:
    """将 memory_store 内部格式 {key: {value: ..., ts: ...}} 展开为 {key: value}。"""
    result = {}
    for k, v in raw.items():
        if isinstance(v, dict) and "value" in v:
            result[k] = v["value"]
        else:
            result[k] = v
    return result


def _compute_feedback_stats(data: dict) -> dict:
    """从 memory.feedback 计算点赞/点踩/跳过统计。"""
    like_count = 0
    dislike_count = 0
    skip_count = 0
    for key, entry in data.items():
        val = entry.get("value", {}) if isinstance(entry, dict) else entry
        if isinstance(val, dict):
            action = val.get("action", "")
            if action == "like":
                like_count += 1
            elif action == "dislike":
                dislike_count += 1
            elif action == "skip":
                skip_count += 1
    return {
        "like_count": like_count,
        "dislike_count": dislike_count,
        "skip_count": skip_count,
    }


def register_http_routes(app: FastAPI):
    """注册所有 HTTP 路由到 FastAPI app。"""

    # ── 1. health ──

    @app.get("/api/health")
    async def health():
        ps = program_state.load_program_state()
        init_mode = InitMode.RESUME
        if ps is None:
            init_mode = InitMode.FIRST_INIT
        elif not program_state.program_date_matches_today(ps):
            init_mode = InitMode.NEW_DAY_INIT
        return ok({"status": "ok", "init_mode": init_mode.value})

    # ── 2. init ──

    @app.get("/api/init")
    async def init():
        settings = settings_store.load()
        netease_status = await _get_netease_login_status()
        profile_raw = memory_store.load_category("profile")
        profile = _unwrap_memory_profile(profile_raw)
        playlists = playlist_store.list_all()
        player_mirror = player_state.load_player_mirror()

        feishu_dev = await _call_music_api("GET", "/api/v1/device/info")
        calendar_connected = False
        if feishu_dev and feishu_dev.get("code") == 0:
            calendar_connected = feishu_dev.get("data", {}).get("feishu_user_logged_in", False)

        return ok({
            "agent": {
                "version": "0.2.0",
                "persona": "night_dj",
            },
            "settings": {
                "llm_apikey": _resolve_llm_key(settings.get("llm_apikey", "")),
                "netease_apikey": settings.get("netease_apikey", ""),
            },
            "netease": netease_status,
            "user_profile": profile,
            "playlists": playlists,
            "player": player_mirror,
            "recent_moods": [],
            "current_state": {
                "is_playing": player_mirror.get("is_playing", False),
                "current_song": player_mirror.get("current_song"),
                "scene": "evening",
                "active_expression": "idle",
            },
            "calendar": {
                "connected": calendar_connected,
                "current_block": "free",
            },
        })

    # ── 3. settings ──

    @app.get("/api/settings")
    async def get_settings():
        s = settings_store.load()
        s["llm_apikey"] = _resolve_llm_key(s.get("llm_apikey", ""))
        return ok(s)

    @app.put("/api/settings")
    async def update_settings(body: SettingsUpdate):
        updates = {}
        if body.llm_apikey is not None:
            updates["llm_apikey"] = body.llm_apikey
        if body.netease_apikey is not None:
            updates["netease_apikey"] = body.netease_apikey
        updated = settings_store.update(**updates)
        return ok(updated)

    # ── 4. playlist ──

    @app.get("/api/playlist/list")
    async def playlist_list():
        return ok({"playlists": playlist_store.list_all()})

    @app.get("/api/playlist/{playlist_id}")
    async def playlist_get(playlist_id: str):
        pl = playlist_store.get(playlist_id)
        if pl is None:
            return fail(1003, "歌单不存在")
        return ok(pl)

    @app.put("/api/playlist/{playlist_id}")
    async def playlist_update(playlist_id: str, body: PlaylistUpdateRequest):
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.remark is not None:
            updates["remark"] = body.remark
        pl = playlist_store.update(playlist_id, updates)
        if pl is None:
            return fail(1003, "歌单不存在")
        return ok(pl)

    @app.delete("/api/playlist/{playlist_id}")
    async def playlist_delete(playlist_id: str):
        ok_ = playlist_store.delete(playlist_id)
        if not ok_:
            return fail(1003, "歌单不存在")
        return ok()

    @app.post("/api/playlist/import")
    async def playlist_import(body: PlaylistImportRequest):
        if not body.playlist_url:
            return fail(1001, "playlist_url 不能为空")
        pl = playlist_store.import_from_url(body.playlist_url)
        return ok(pl)

    # ── 5. user ──

    @app.get("/api/user/profile")
    async def user_profile():
        raw = memory_store.load_category("profile")
        return ok(_unwrap_memory_profile(raw))

    @app.put("/api/user/baseinfo")
    async def user_baseinfo(body: UserBaseInfoUpdate):
        if body.nickname:
            memory_store.write("profile", "nickname", body.nickname)
        if body.avatar_url:
            memory_store.write("profile", "avatar_url", body.avatar_url)
        raw = memory_store.load_category("profile")
        return ok(_unwrap_memory_profile(raw))

    @app.post("/api/user/analyze")
    async def user_analyze():
        """手动触发 AI 分析全部本地歌单，生成/更新用户音乐画像。

        MVP：mock 实现，写入占位画像数据。
        P2：调 LLMService 分析歌单。
        """
        now_ms = int(time.time() * 1000)
        memory_store.write("profile", "favorite_genres", ["pop", "rock", "electronic"])
        memory_store.write("profile", "favorite_artists", [])
        memory_store.write("profile", "music_preference_desc", "偏好流行、摇滚和电子音乐")
        memory_store.write("profile", "AI_conclustion", "热爱多元曲风，喜欢探索新音乐")
        memory_store.write("profile", "update_at", now_ms)
        return ok({"update_at": now_ms})

    # ── 6. feedback ──

    @app.get("/api/feedback")
    async def feedback_list():
        raw = memory_store.load_category("feedback")
        records = []
        for key, entry in raw.items():
            val = entry.get("value", {}) if isinstance(entry, dict) else entry
            records.append({
                "id": key,
                "action": val.get("action", "") if isinstance(val, dict) else "",
                "song_id": val.get("song_id", "") if isinstance(val, dict) else "",
                "ts": entry.get("ts", 0) if isinstance(entry, dict) else 0,
            })
        return ok({"records": records, "total": len(records)})

    @app.get("/api/feedback/stats")
    async def feedback_stats():
        raw = memory_store.load_category("feedback")
        stats = _compute_feedback_stats(raw)
        return ok(stats)

    @app.post("/api/feedback")
    async def feedback_submit(body: FeedbackRequest):
        """提交对当前歌曲的反馈 — 写入 memory feedback 分类。"""
        if body.action not in ("like", "dislike", "skip", "favorite"):
            return fail(1001, f"不支持的 action: {body.action}")
        if not body.song_id:
            return fail(1001, "song_id 不能为空")
        ts = body.ts if body.ts > 0 else int(time.time() * 1000)
        ok_ = memory_store.write("feedback", body.song_id, {
            "action": body.action,
            "song_id": body.song_id,
        })
        if not ok_:
            return fail(9999, "写入反馈失败")
        return ok({"recorded": True, "ts": ts})

    # ── 7. memory ──

    @app.get("/api/memory/query")
    async def memory_query(key: Optional[str] = Query(None), category: Optional[str] = Query(None)):
        """查询 Memory。支持按 key 和 category 过滤。"""
        if category and category not in ("profile", "preference", "context", "feedback"):
            return fail(1001, f"不支持的 category: {category}")
        source_map = {"profile": "user_input", "preference": "inferred", "context": "inferred", "feedback": "feedback"}
        memories = []
        if category and key:
            # 指定 category + key
            raw = memory_store.load_category(category)
            entry = raw.get(key)
            if entry and isinstance(entry, dict) and "value" in entry:
                memories.append({
                    "key": key, "category": category, "value": entry["value"],
                    "confidence": 0.9, "source": source_map.get(category, "user_input"),
                    "updated_at": entry.get("ts", 0),
                })
        elif category:
            # 仅指定 category
            raw = memory_store.load_category(category)
            for k, v in raw.items():
                if isinstance(v, dict) and "value" in v:
                    memories.append({
                        "key": k, "category": category, "value": v["value"],
                        "confidence": 0.9, "source": source_map.get(category, "user_input"),
                        "updated_at": v.get("ts", 0),
                    })
        elif key:
            # 仅指定 key — 搜索所有 category
            all_data = memory_store.load_all()
            for cat_name, cat_data in all_data.items():
                if isinstance(cat_data, dict) and key in cat_data:
                    entry = cat_data[key]
                    if isinstance(entry, dict) and "value" in entry:
                        memories.append({
                            "key": key, "category": cat_name, "value": entry["value"],
                            "confidence": 0.9, "source": source_map.get(cat_name, "user_input"),
                            "updated_at": entry.get("ts", 0),
                        })
        else:
            # 返回全部
            all_data = memory_store.load_all()
            for cat_name, cat_data in all_data.items():
                if isinstance(cat_data, dict):
                    for k, v in cat_data.items():
                        if isinstance(v, dict) and "value" in v:
                            memories.append({
                                "key": k, "category": cat_name, "value": v["value"],
                                "confidence": 0.9, "source": source_map.get(cat_name, "user_input"),
                                "updated_at": v.get("ts", 0),
                            })
        return ok({"memories": memories})

    @app.post("/api/memory/update")
    async def memory_update(body: MemoryUpdateRequest):
        """写入/更新一条 Memory。"""
        if body.category not in ("profile", "preference", "context", "feedback"):
            return fail(1001, f"不支持的 category: {body.category}")
        if not body.key:
            return fail(1001, "key 不能为空")
        ok_ = memory_store.write(body.category, body.key, body.value)
        if not ok_:
            return fail(9999, "写入 Memory 失败")
        return ok({"updated": True, "ts": int(time.time() * 1000)})

    @app.delete("/api/memory/{key}")
    async def memory_delete(key: str, category: str = Query("preference")):
        """删除一条 Memory。"""
        if category not in ("profile", "preference", "context", "feedback"):
            return fail(1001, f"不支持的 category: {category}")
        ok_ = memory_store.delete(category, key)
        if not ok_:
            return fail(1003, "Memory 不存在")
        return ok({"deleted": True})

    # ── 8. history ──

    @app.get("/api/history/songs")
    async def history_songs(limit: int = 20, offset: int = 0):
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        result = player_state.load_history(limit=limit, offset=offset)
        return ok(result)

    # ── 9. netease ──

    @app.post("/api/netease/login")
    async def netease_login(body: NeteaseLoginRequest):
        """网易云登录 — 代理到 music_agent_api。"""
        if body.type == "phone":
            if not body.phone or not body.password:
                return fail(1001, "手机号和密码不能为空")
            result = await _call_music_api("POST", "/api/v1/login/phone", {
                "phone": body.phone, "password": body.password,
            })
        elif body.type == "qr":
            if not body.token:
                return fail(1001, "QR token 不能为空")
            result = await _call_music_api("POST", "/api/v1/login/qr-check", {
                "key": body.token,
            })
        else:
            return fail(1001, "不支持的登录类型")

        if result and result.get("code") == 0:
            return ok(result.get("data", {}))
        msg = result.get("msg", "登录失败") if result else "网易云服务不可用"
        return fail(3002, msg)

    @app.get("/api/netease/status")
    async def netease_status():
        status = await _get_netease_login_status()
        return ok(status)

    @app.get("/api/netease/qr-key")
    async def netease_qr_key():
        """获取 QR 登录临时 key。"""
        result = await _call_music_api("GET", "/api/v1/login/qr-key")
        if result and result.get("code") == 0:
            return ok(result.get("data", {}))
        return fail(3002, result.get("msg", "获取 QR key 失败") if result else "网易云服务不可用")

    @app.get("/api/netease/qr-create")
    async def netease_qr_create(key: str = Query(..., description="QR key")):
        """生成 QR 码 base64 图片。"""
        result = await _call_music_api("GET", "/api/v1/login/qr-create", {"key": key})
        if result and result.get("code") == 0:
            return ok(result.get("data", {}))
        return fail(3002, result.get("msg", "生成 QR 码失败") if result else "网易云服务不可用")

    @app.post("/api/netease/qr-check")
    async def netease_qr_check(body: QrCheckRequest):
        """轮询检查 QR 码扫描状态。"""
        result = await _call_music_api("POST", "/api/v1/login/qr-check", {"key": body.key})
        if result and result.get("code") == 0:
            return ok(result.get("data", {}))
        return fail(3002, result.get("msg", "检查 QR 码状态失败") if result else "网易云服务不可用")

    # ── 10. proxy ──

    @app.get("/api/proxy/audio")
    async def proxy_audio(url: str = Query(..., description="网易云 CDN 音频 URL")):
        """代理网易云音频流，解决前端 CORS / Referer 限制。"""
        if not url.startswith("http"):
            return fail(1001, "无效的音频 URL")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"Referer": "https://music.163.com"},
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    return fail(3002, f"音频获取失败: HTTP {resp.status_code}")
                content_type = resp.headers.get("content-type", "audio/mpeg")
                # 检测 CDN 返回了 HTML（常见于 URL 过期或权限不足）
                if content_type.startswith("text/html"):
                    logger = __import__("logging").getLogger(__name__)
                    logger.warning("Audio proxy: CDN returned HTML for url=%s", url[:80])
                    return fail(3002, "音频不可用：CDN 返回了网页（可能已过期或需付费）")
                return StreamingResponse(
                    resp.aiter_bytes(),
                    media_type=content_type,
                    headers={
                        "Accept-Ranges": "bytes",
                        "Cache-Control": "public, max-age=3600",
                    },
                )
        except httpx.RequestError as e:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Audio proxy request failed: %s", e)
            return fail(3002, "音频获取失败: 网络错误")


    # ── 11. feishu ──

    @app.get("/api/feishu/status")
    async def feishu_status():
        """飞书日历连接状态。"""
        result = await _call_music_api("GET", "/api/v1/device/info")
        if result and result.get("code") == 0:
            data = result.get("data", {})
            return ok({"connected": data.get("feishu_user_logged_in", False)})
        return ok({"connected": False})

    @app.get("/api/feishu/auth/url")
    async def feishu_auth_url():
        """获取飞书 OAuth 扫码授权 URL。"""
        result = await _call_music_api("GET", "/api/v1/feishu/auth/url")
        if result and result.get("code") == 0:
            return ok(result.get("data", {}))
        return fail(3002, result.get("msg", "获取飞书授权 URL 失败") if result else "飞书服务不可用")

    @app.get("/api/feishu/calendar/today")
    async def feishu_calendar_today():
        """获取今日日程摘要。"""
        result = await _call_music_api("GET", "/api/v1/feishu/calendar/primary/events")
        if result and result.get("code") == 0:
            data = result.get("data", {})
            items = data.get("items", [])
            return ok({
                "date": time.strftime("%Y-%m-%d"),
                "event_count": len(items),
                "tags": list({e.get("summary", "") for e in items if e.get("summary")}),
                "is_busy": len(items) > 0,
                "source": "feishu",
            })
        from agent.services.feishu_service import feishu_service as _fs
        return ok(await _fs.get_calendar_today())

    @app.get("/api/feishu/calendar/current")
    async def feishu_calendar_current():
        """获取当前进行中的日程。"""
        now_ts = int(time.time())
        result = await _call_music_api("GET", "/api/v1/feishu/calendar/primary/events", {
            "start_time": str(now_ts - 7200),
            "end_time": str(now_ts + 7200),
        })
        if result and result.get("code") == 0:
            data = result.get("data", {})
            for item in data.get("items", []):
                start_ts = item.get("start", {}).get("timestamp", "")
                end_ts = item.get("end", {}).get("timestamp", "")
                if start_ts and end_ts:
                    try:
                        s, e = int(start_ts), int(end_ts)
                        if s <= now_ts <= e:
                            return ok({
                                "has_event": True,
                                "title": item.get("summary", ""),
                                "location": item.get("location", ""),
                                "participants": [p.get("display_name", "") for p in item.get("attendees", [])],
                                "start_time": item.get("start", {}).get("datetime", ""),
                                "end_time": item.get("end", {}).get("datetime", ""),
                                "source": "feishu",
                            })
                    except ValueError:
                        pass
            return ok({"has_event": False, "title": "", "location": "", "participants": [],
                       "start_time": "", "end_time": "", "source": "feishu"})
        from agent.services.feishu_service import feishu_service as _fs
        return ok(await _fs.get_calendar_current())

    @app.post("/api/feishu/refresh")
    async def feishu_refresh():
        """刷新飞书日历缓存（当前为 no-op）。"""
        return ok()


def _resolve_llm_key(stored_key: str) -> str:
    """返回有效的 LLM API Key：优先 settings.json 存储值，其次 .env 配置值。"""
    if stored_key:
        return stored_key
    env_key = config_settings.DEEPSEEK_API_KEY
    if env_key:
        return env_key
    return ""
