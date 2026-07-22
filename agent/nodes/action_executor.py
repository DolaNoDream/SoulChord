"""Action Executor 节点 — 消费 actions[]，执行具体操作。

★ v0.6.1 B 项：action_planner 是唯一 action_owner（产生 actions）
★ 本节点是 action_consumer（执行 actions，不产生新 actions）
★ 职责：将 actions 执行结果回填到 pending_payload，供 emit_response 发送

action	执行方	pending_payload 重写字段
tts_speak	TTSService.synthesize	transition_speech.{audio_url, duration_ms, provider}
play_song	MusicService.get_play_url	music_play.play_url
update_program	ProgramService（预留 P1）	—
set_volume	预留 P1	—
"""

import copy
import json
import logging
import os
import urllib.parse

from agent.services.tts_service import TTSService, tts_service as _tts
from agent.services.music_service import MusicService

logger = logging.getLogger(__name__)

# 模块级 Service 实例（非 Tool 层，不需要经 adapter）
_music = MusicService()


async def action_executor_node(state: dict) -> dict:
    """消费 state.actions，执行具体操作。

    遍历 actions[]，按 type 分派到对应 Service：
      - tts_speak → TTSService.synthesize
      - play_song → MusicService.get_play_url
      - 未知 type → 安全跳过

    Returns:
        dict（partial update）：
          - pending_payload（被 enrich 后的 payload）
          - last_error（可选，执行失败时设置，不阻塞 graph）
    """
    actions = state.get("actions", []) or []
    if not actions:
        # 无 actions 时透传原有 pending_payload
        return {"pending_payload": state.get("pending_payload") or {}}

    # 深拷贝 payload 避免副作用
    pending_payload = copy.deepcopy(state.get("pending_payload") or {})
    last_error = None
    needs_replan = False

    for action in actions:
        action_type = action.get("type", "")
        params = action.get("params", {}) or {}

        if action_type == "tts_speak":
            _error = await _exec_tts(pending_payload, params)
            if _error:
                last_error = _error

        elif action_type == "play_song":
            _error = await _exec_play(pending_payload, params)
            if _error:
                last_error = _error
                # 歌曲不可播 → 清理 music_play + 从队列移除（避免后续重复尝试）
                pending_payload.pop("music_play", None)
                _pop_failed_from_queue(state, params.get("song_id", ""))
                needs_replan = True
                break  # 跳过剩余 actions

            # ★ 更新 RDS current_song（DJ Host backstop 需要实时 current_song）
            _update_rds_current_song(state, params, pending_payload)

        else:
            logger.debug("ActionExecutor: unknown action type=%s (skip)", action_type)

    result = {"pending_payload": pending_payload}
    if last_error:
        result["last_error"] = last_error
    if needs_replan:
        refs = state.get("__refs__") or {}
        event_svc = refs.get("event_service")
        if event_svc is not None:
            song_id = params.get("song_id", "?")
            await event_svc.push_replan(f"song_unplayable:{song_id}")
            logger.warning("ActionExecutor: pushed REPLAN_REQUEST (song=%s unplayable)", song_id)
        else:
            logger.warning("ActionExecutor: event_service not injected in __refs__")
    return result


async def _exec_tts(pending_payload: dict, params: dict) -> dict | None:
    """执行 tts_speak action。"""
    text = params.get("text", "")
    if not text:
        logger.warning("ActionExecutor: tts_speak with empty text, skip")
        return None

    try:
        result = await _tts.synthesize(text)
        # enrich transition_speech
        ts = pending_payload.get("transition_speech") or {}
        ts["audio_url"] = result["audio_url"]
        ts["duration_ms"] = result["duration_ms"]
        ts["provider"] = result["provider"]
        pending_payload["transition_speech"] = ts
        has_audio = "yes" if result.get("audio_url") else "NO"
        logger.info("ActionExecutor: tts_speak done (provider=%s audio=%s duration=%dms text_len=%d)",
                     result.get("provider", "?"), has_audio, result["duration_ms"], len(text))
        return None
    except Exception as e:
        logger.error("ActionExecutor: tts_speak failed: %s", e)
        return {"code": "TTS_FAILED", "message": str(e)}


async def _exec_play(pending_payload: dict, params: dict) -> dict | None:
    """执行 play_song action。"""
    song_id = params.get("song_id", "")
    if not song_id:
        logger.warning("ActionExecutor: play_song with empty song_id, skip")
        return None

    try:
        play_url = await _music.get_play_url(song_id)
        if not play_url:
            logger.error("ActionExecutor: play_url is None for song=%s", song_id)
            return {"code": "PLAY_URL_NOT_FOUND", "message": f"No playable URL for {song_id}"}

        # ★ 将原始 CDN URL 转为代理 URL，解决前端 CORS / 跨域问题
        from agent.config import settings as _settings
        encoded = urllib.parse.quote(play_url, safe="")
        proxy_url = f"http://localhost:{_settings.AGENT_PORT}/api/proxy/audio?url={encoded}"

        # enrich music_play
        mp = pending_payload.get("music_play") or {}
        mp["play_url"] = proxy_url
        pending_payload["music_play"] = mp

        # ★ 写入播放历史
        song = mp.get("song") or {}
        _record_history(song_id, song)

        # ★ 将当前播放状态写入 player_mirror.json，
        #   供前端的 WS 连接恢复（INIT 流程的 WS 消息早于前端连接，会被丢弃）
        _save_playback_state_to_mirror(song_id, mp.get("song", {}), proxy_url)

        logger.info("ActionExecutor: play_song done (song=%s) → proxy OK", song_id)
        return None
    except Exception as e:
        logger.error("ActionExecutor: play_song failed: %s", e)
        return {"code": "PLAY_FAILED", "message": str(e)}


def _record_history(song_id: str, song: dict):
    """将播放记录写入 player_history.json。"""
    artist_name = ""
    artists = song.get("artists") or []
    if isinstance(artists, list) and len(artists) > 0:
        a0 = artists[0]
        artist_name = a0.get("name", "") if isinstance(a0, dict) else str(a0)
    elif song.get("artist"):
        artist_name = song["artist"] if isinstance(song["artist"], str) else ""

    entry = {
        "song_id": song_id,
        "song_name": song.get("name", "未知歌曲"),
        "artist": artist_name,
        "cover_url": song.get("cover_url", ""),
        "played_at": int(__import__("time").time() * 1000),
        "feedback": "",
        "duration_played_ms": 0,
    }
    from agent.state.player_state import append_history_entry
    append_history_entry(entry)


def _pop_failed_from_queue(state: dict, failed_song_id: str):
    """播放失败时，从 playlist_queue 移除已失败的歌曲，避免后续重复尝试。"""
    rds = state.get("dependencies", {}).get("runtime_dj_state")
    if not rds:
        return
    queue = rds.get("playlist_queue", []) or []
    if not queue:
        return
    first = queue[0]
    first_id = first.get("song_id") or first.get("id", "")
    if first_id == failed_song_id:
        rds["playlist_queue"] = queue[1:]
        from agent.state.player_state import update_player_event as _upd
        _upd({
            "subtype": "playlist_changed",
            "playlist": rds["playlist_queue"],
            "strategy": {},
        })
        logger.info("Popped failed song=%s from playlist_queue, %d remaining",
                     failed_song_id, len(rds["playlist_queue"]))


def _save_playback_state_to_mirror(song_id: str, song: dict, play_url: str):
    """将当前播放状态写入 player_mirror.json。

    INIT 流程的 WS 消息早于前端连接到达，会被静默丢弃。
    此处将播放状态持久化，供前端 WS 连接时恢复播放。
    """
    # 防御：不缓存测试歌曲
    song_name = (song.get("name") or "").strip()
    if song_name in ("测试歌曲", "测试", "Song 1", "Song1", "Next", "Test Song", "test"):
        logger.info("skip caching test song=%r to player_mirror", song_name)
        return
    from agent.state.player_state import load_player_mirror, DEFAULT_PLAYER_MIRROR
    from agent.config import settings as _settings
    mirror = load_player_mirror() or dict(DEFAULT_PLAYER_MIRROR)
    mirror["current_song"] = song
    mirror["play_url"] = play_url
    mirror["is_playing"] = True
    mirror["current_position_ms"] = 0
    mirror["updated_at_ms"] = int(__import__("time").time() * 1000)
    # 保持原有的 queue 信息不覆盖
    try:
        os.makedirs(os.path.dirname(_settings.PLAYER_MIRROR_FILE), exist_ok=True)
        with open(_settings.PLAYER_MIRROR_FILE, "w", encoding="utf-8") as f:
            json.dump(mirror, f, ensure_ascii=False, indent=2)
    except OSError:
        logger.warning("Failed to write playback state to player_mirror")


def _update_rds_current_song(state: dict, params: dict, pending_payload: dict):
    """更新 RDS current_song，供 DJ Host backstop 使用。

    RDS current_song 仅在启动时从 player_mirror.json 加载，
    运行时默认不更新。此函数在每首歌播放成功后同步更新 RDS。
    """
    rds = state.get("dependencies", {}).get("runtime_dj_state")
    if not rds:
        return
    song_id = params.get("song_id", "")
    if not song_id:
        return
    mp = pending_payload.get("music_play") or {}
    song = mp.get("song") or {}
    artists = song.get("artists", [])
    artist_str = (
        ", ".join(a.get("name", "") for a in artists)
        if artists else song.get("artist", "")
    )
    rds["current_song"] = {
        "song_id": song_id,
        "name": song.get("name", "未知歌曲"),
        "artist": artist_str,
    }
    logger.debug("RDS current_song updated: %s — %s",
                 rds["current_song"].get("name"), song_id)

