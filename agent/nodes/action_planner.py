"""Action Planner 节点 — 唯一 action_owner。

★ v0.1.1 B 项：唯一 action_owner（决定**如何执行**）
★ v0.1.2 P0-4：actions 使用默认 replace（整数组返回，无 reducer）
★ v0.1.2 P0-3：RuntimeDJState 修改经 state_manager.program / state_manager.player
★ v0.1.2 P0-1：return dict（partial update）
★ v0.6 D 项 + ★ v0.1.1 E 项：song_finished queue 空生成 transition speech
"""

import logging
import time

from agent.state.state_manager import state_manager
from agent.state.runtime_dj_state import sync_from_program_state
from agent.shared.enums import TriggerType, PlayerEventSubtype, ProgramMood

logger = logging.getLogger(__name__)

# ★ 已知真实的网易云 song_id（当 LLM 搜索为空时兜底播放）
_REAL_FALLBACK_SONGS = [
    {"song_id": "108914", "name": "江南", "artist": "林俊杰"},
    {"song_id": "25642214", "name": "爱错(Live)", "artist": "王力宏"},
    {"song_id": "26548584", "name": "Happy", "artist": "Pharrell Williams"},
    {"song_id": "28403111", "name": "特别的人", "artist": "方大同"},
    {"song_id": "3339230677", "name": "晴天", "artist": "周杰伦"},
    {"song_id": "4336330", "name": "Here Comes The Sun", "artist": "The Beatles"},
]


async def action_planner_node(state: dict) -> dict:
    """Action Planner 主节点。

    路由到各触发器对应的处理分支。
    """
    trigger_type = state.get("trigger_type", "")
    init_plan = state.get("init_plan")

    # ★ system_init + init_plan 存在 → Init Planner 路径
    if trigger_type == TriggerType.SYSTEM_INIT and init_plan:
        return await _handle_init_plan(state, init_plan)

    # ★ v0.6 D 项：player_event.song_finished → action_planner（不进 feedback_extractor）
    # ★ v8.2：play_end / user_skip → 也触发 _handle_song_finished（队列空时 REPLAN）
    if trigger_type == TriggerType.PLAYER_EVENT:
        subtype = (state.get("trigger_event") or {}).get("subtype", "")
        if subtype == PlayerEventSubtype.SONG_FINISHED.value:
            return await _handle_song_finished(state)
        if subtype in ("play_end", "user_skip", "skip"):
            # feedback_extractor 已先于 action_planner 执行（graph 边保证），
            # feedback 已记录，此处只需处理换歌逻辑
            return await _handle_song_finished(state)

    # conversation / timer_event / replan_event — 从 llm_decision 转换
    if trigger_type in (
        TriggerType.CONVERSATION.value,
        TriggerType.TIMER_EVENT.value,
        TriggerType.REPLAN_EVENT.value,
    ):
        return await _handle_llm_decision(state)

    # 其他（system / user_control）— 非本 spec 范围，返回空
    return {
        "actions": [],
        "pending_payload": None,
        "should_speak": False,
        "should_play_music": False,
    }


async def _handle_init_plan(state: dict, init_plan: dict) -> dict:
    """处理 init_plan：应用 ProgramState + 准备 play + welcome。

    ★ Q14+15 事务顺序（用户拍板）：
      ① save_program_state
      ② play_music
      ③ emit status.welcome
      ④ emit chat.reply
      ⑤ emit music.play

    重要：LLM 可能输出虚假 song_id（UUID 或空字符串），
    此处会验证并替换为预置的真实歌曲列表。
    """
    program_state = init_plan.get("program_state", {})
    first_song_id = init_plan.get("first_song_id")
    initial_playlist = init_plan.get("initial_playlist", [])
    welcome_text = init_plan.get("welcome_text", "")

    # ★ 修复：LLM 生成的 init_plan 中 song_id 可能是虚假的（UUID / 空字符串），
    #   此时 action_executor 调 get_play_url 会失败 → 无歌可播。
    #   检查 first_song_id，若为假则替换整个 initial_playlist 为预置真实歌曲。
    if initial_playlist and _is_fake_song_id(first_song_id or ""):
        logger.info("init_plan: first_song_id=%r is fake, replacing entire playlist with real fallback songs", first_song_id)
        initial_playlist = list(_REAL_FALLBACK_SONGS)
        first_song_id = initial_playlist[0]["song_id"] if initial_playlist else ""

    # ① 写入 program_state.json + 同步 RuntimeDJState
    save_ok = state_manager.program.save_program_state(program_state)
    if save_ok:
        rds = state.get("dependencies", {}).get("runtime_dj_state")
        if rds is not None:
            sync_from_program_state(rds, program_state)

    now_ts = int(time.time() * 1000)

    # 构造 actions（②～⑤ 顺序）
    first_idx = 0
    first_song = None
    for i, s in enumerate(initial_playlist):
        if s.get("song_id", s.get("id")) == first_song_id:
            first_song = s
            first_idx = i
            break
    if not first_song and initial_playlist:
        first_song = initial_playlist[0]

    actions = []
    if first_song:
        song_id = first_song.get("song_id") or first_song.get("id", "")
        actions.append({
            "type": "play_song",
            "params": {"song_id": song_id, "auto_play": True},
            "reason": "init_plan_first_song",
        })

    # ★ 初始播放列表剩余歌曲存入 queue（第一首歌之后的所有歌曲）
    #   过滤虚假 song_id + 补满至少 5 首可播歌曲
    if initial_playlist and first_song:
        first_sid = first_song.get("song_id") or first_song.get("id", "")
        remaining_raw = [s for i, s in enumerate(initial_playlist) if i != first_idx]

        # 过滤：只保留真实 song_id 的歌曲
        valid_remaining = [s for s in remaining_raw if not _is_fake_song_id(s.get("song_id") or s.get("id", ""))]
        logger.info("init_plan: %d/%d remaining songs have valid song_id", len(valid_remaining), len(remaining_raw))

        # 用 _REAL_FALLBACK_SONGS 补满至少 5 首（跳过与第一首重复的）
        fallback_pool = [s for s in _REAL_FALLBACK_SONGS if s["song_id"] != first_sid]
        padded = valid_remaining + fallback_pool
        final_queue = _to_queue_songs(padded[:max(5, len(valid_remaining))])

        rds = state.get("dependencies", {}).get("runtime_dj_state")
        if rds:
            rds["playlist_queue"] = final_queue
            state_manager.player.update_player_event({
                "subtype": "playlist_changed",
                "playlist": final_queue,
                "strategy": {"source": "init_plan"},
            })
            logger.info("Stored %d songs in playlist_queue from init_plan (%d valid + fallback)",
                        len(final_queue), len(valid_remaining))

    # 转为前端 Song 格式（WS music.play.payload.song）
    ws_song = _to_frontend_song(first_song) if first_song else None

    # 状态更新 + welcome
    pending_payload = {
        "chat_reply": welcome_text,
        "status_update": {
            "type": "welcome",
            "init_mode": state.get("init_mode", "first_init"),
            "program_state": program_state,
            "ts": now_ts,
        },
    }
    if ws_song:
        pending_payload["music_play"] = {
            "song": ws_song,
            "auto_play": True,
        }

    return {
        "actions": actions,
        "pending_payload": pending_payload,
        "should_speak": True,
        "should_play_music": bool(first_song is not None),
    }


async def _handle_song_finished(state: dict) -> dict:
    """处理 song_finished 事件。

    ★ v0.6 D 项 + ★ v0.1.1 E 项 + ★ v0.1.2 P1-5：
    - queue 有下一首 → play_song(next)，不写 feedback
    - queue 空 → transition speech + 推 REPLAN_REQUEST

    重要：只读 runtime_snapshot.playlist_queue，不修改 snapshot。
    Mirror 不是 source of truth，等 ws/handler 反馈。
    """
    snapshot = state.get("runtime_snapshot") or {}
    playlist_queue = snapshot.get("playlist_queue", [])
    program = state.get("program") or {}
    next_song = playlist_queue[0] if playlist_queue else None

    if next_song:
        song_id = next_song.get("song_id") or next_song.get("id", "")
        ws_song = _to_frontend_song(next_song)

        # ★ 消费队列：移除已播放的歌曲（更新 live RDS + mirror）
        rds = state.get("dependencies", {}).get("runtime_dj_state")
        if rds and rds.get("playlist_queue"):
            rds["playlist_queue"] = rds["playlist_queue"][1:]
            state_manager.player.update_player_event({
                "subtype": "playlist_changed",
                "playlist": rds["playlist_queue"],
                "strategy": rds.get("queue_strategy", {}),
            })
            logger.info("Consumed playlist_queue, %d songs remaining", len(rds["playlist_queue"]))

        return {
            "actions": [{
                "type": "play_song",
                "params": {"song_id": song_id, "auto_play": True},
                "reason": "song_finished_queue_next",
            }],
            "pending_payload": {
                "music_play": {"song": ws_song, "auto_play": True},
            },
            "should_play_music": True,
            "should_speak": False,
            "feedback_record": None,
        }

    # queue 空 → transition speech + 推 REPLAN_REQUEST
    refs = state.get("__refs__") or {}
    event_svc = refs.get("event_service")
    replan_ok = True
    if event_svc is not None:
        replan_ok = await event_svc.push_replan("queue_empty_after_song_finished")
    else:
        logger.warning("event_service not injected in __refs__, cannot push REPLAN_REQUEST")

    transition_text = _generate_transition_speech(snapshot, program)

    result = {
        "actions": [{
            "type": "tts_speak",
            "params": {"text": transition_text},
            "reason": "queue_empty_transition",
        }],
        "pending_payload": {
            "transition_speech": {
                "text": transition_text,
                "source": "song_finished_queue_empty",
                "mood": snapshot.get("program_mood", "neutral"),
                "theme": program.get("today_theme", ""),
            },
        },
        "should_speak": True,
        "should_play_music": False,
        "feedback_record": None,
    }

    if not replan_ok:
        result["last_error"] = {
            "code": "REPLAN_PUSH_FAILED",
            "message": "Failed to push REPLAN_REQUEST after song_finished",
        }

    return result


async def _handle_llm_decision(state: dict) -> dict:
    """将 LLM decision 转换为 actions + pending_payload。

    适用 trigger：conversation / timer_event / replan_event。
    LLM 输出 4 块结构：program_decision / playlist_decision / dialogue_decision / tool_calls

    优先使用 tool_messages 中的真实搜索结果（避免 LLM 编造 song_id）。
    """
    decision = state.get("llm_decision") or {}
    dialogue = decision.get("dialogue_decision", {}) or {}
    playlist_dec = decision.get("playlist_decision", {}) or {}

    should_speak = dialogue.get("should_speak", False)
    text = dialogue.get("text", "")

    # 构造 pending_payload
    pending_payload = {}
    if should_speak and text:
        pending_payload["chat_reply"] = text

    # 构造 actions（仅 play_song 需要）
    actions = []
    playlist_action = playlist_dec.get("action", "keep")
    songs = playlist_dec.get("songs", []) or []

    logger.info("LLM decision: action=%s songs=%d should_speak=%s",
                playlist_action, len(songs), should_speak)

    # 当 action 为 replace/add 且有歌曲时 → 播放第一首
    # prompt 定义有效值：keep / replace / add（不是 "play"）
    if playlist_action in ("replace", "add") and songs:
        song = songs[0]
        # ★ prompt 要求 LLM 输出 song_id, 搜索结果是 id，兼容两者
        song_id = song.get("id") or song.get("song_id", "")

        # ★ 仅在 LLM 编造 song_id 时回退到搜索结果的第一首
        # （LLM 编造的 song_id 通常是字母组合，真实网易云 ID 是纯数字）
        if _is_fake_song_id(song_id):
            real_song = _get_real_search_result(state)
            if real_song:
                logger.info("ActionPlanner: fake song_id=%s, fallback to search result id=%s",
                            song_id, real_song.get("id"))
                song = real_song
                song_id = real_song.get("id", song_id)
        else:
            logger.debug("ActionPlanner: using LLM-chosen song_id=%s", song_id)

        # ★ 校验 song_id（二次防线：拒绝漏网的虚假 ID）
        if song_id and _is_fake_song_id(song_id):
            logger.warning("ActionPlanner: rejecting fake song_id=%s, will fallback to tts", song_id)
            song_id = ""
            song = {}

        if song_id:
            actions.append({
                "type": "play_song",
                "params": {"song_id": song_id, "auto_play": True},
                "reason": f"llm_decision_{playlist_action}",
            })
            pending_payload["music_play"] = {
                "song": _to_frontend_song(song) if song else None,
                "auto_play": True,
            }
            # ★ 将 LLM 输出的剩余歌曲存入 playlist_queue，实现自动连播
            #   即使 LLM 只输出了 1 首歌，也用 fallback 补满队列
            remaining_raw = songs[1:]  # 可能为空
            # 过滤虚假 song_id + 补满至少 3 首
            valid = [s for s in remaining_raw if not _is_fake_song_id(s.get("id") or s.get("song_id", ""))]
            if remaining_raw:
                logger.info("llm_decision: %d/%d remaining songs valid", len(valid), len(remaining_raw))
            # 如果有效歌曲不足 3 首，从 fallback 补
            first_sid = song_id if song_id else ""
            fallback_pool = [dict(s) for s in _REAL_FALLBACK_SONGS if s["song_id"] != first_sid]
            final_queue = _to_queue_songs(valid + fallback_pool)[:10]
            rds = state.get("dependencies", {}).get("runtime_dj_state")
            if rds:
                if playlist_action == "add":
                    existing = rds.get("playlist_queue", []) or []
                    # 追加前过滤 existing 中的虚假 ID
                    existing = [s for s in existing if not _is_fake_song_id(s.get("song_id") or s.get("id", ""))]
                    rds["playlist_queue"] = existing + final_queue
                else:
                    rds["playlist_queue"] = final_queue
                state_manager.player.update_player_event({
                    "subtype": "playlist_changed",
                    "playlist": rds["playlist_queue"],
                    "strategy": {"source": "llm_decision", "action": playlist_action},
                })
                logger.info("Stored %d songs in playlist_queue from LLM decision (action=%s)",
                            len(final_queue), playlist_action)
            else:
                logger.warning("Cannot store playlist_queue: runtime_dj_state not in dependencies")
        elif should_speak:
            # song_id 被拒，但 LLM 计划了说话 → 把 fallback 信息加进 dialogue
            fallback_text = (
                f"{text.rstrip('。')}，不过我没有找到可播放的歌曲，"
                "让我重新搜索一下。"
            ) if text else "我没有找到可播放的歌曲，正在重新搜索..."
            pending_payload["chat_reply"] = fallback_text

    # ★ LLM 输出 add/replace 但 songs=0 → 尝试从工具搜索结果或硬编码兜底中提取歌曲
    #   （场景：REPLAN 搜索后 LLM 仍认为无歌 / 搜索返回空）
    if playlist_action in ("replace", "add") and not pending_payload.get("music_play"):
        fallback_song = _get_fallback_song(state)
        if fallback_song:
            song_id = fallback_song.get("song_id") or fallback_song.get("id", "")
            if song_id and not _is_fake_song_id(song_id):
                actions.append({
                    "type": "play_song",
                    "params": {"song_id": song_id, "auto_play": True},
                    "reason": f"fallback_{playlist_action}_empty",
                })
                pending_payload["music_play"] = {
                    "song": _to_frontend_song(fallback_song),
                    "auto_play": True,
                }
                # 用 fallback 列表填充队列
                _fill_queue_with_fallback(state, song_id)
                logger.info("ActionPlanner: fallback play song_id=%s (LLM output 0 songs)", song_id)

    # ★ LLM 输出 keep + songs=0 → 队列空，仍需要播放歌曲
    if playlist_action == "keep" and not songs and not pending_payload.get("music_play"):
        fallback_song = _get_fallback_song(state)
        if fallback_song:
            song_id = fallback_song.get("song_id") or fallback_song.get("id", "")
            if song_id and not _is_fake_song_id(song_id):
                actions.append({
                    "type": "play_song",
                    "params": {"song_id": song_id, "auto_play": True},
                    "reason": "fallback_keep_empty",
                })
                pending_payload["music_play"] = {
                    "song": _to_frontend_song(fallback_song),
                    "auto_play": True,
                }
                _fill_queue_with_fallback(state, song_id)
                logger.info("ActionPlanner: fallback play song_id=%s (LLM keep + 0 songs)", song_id)

    return {
        "actions": actions,
        "pending_payload": pending_payload if pending_payload else None,
        "should_speak": should_speak,
        "should_play_music": bool(pending_payload.get("music_play")),
    }


def _get_real_search_result(state: dict) -> dict | None:
    """从 tool_messages 提取最近一条 play_music 的真实搜索结果。"""
    tool_msgs = state.get("tool_messages", []) or []
    # 从后往前找最近一次 play_music（搜索）结果
    for msg in reversed(tool_msgs):
        if msg.get("name") == "play_music":
            result = msg.get("result", {})
            songs = result.get("songs", []) if isinstance(result, dict) else []
            if songs:
                return songs[0]
    return None


def _get_fallback_song(state: dict) -> dict | None:
    """LLM 输出 0 首歌曲时，尝试 3 级兜底。

    优先级：
      1. 从 tool_messages 中提取最近搜索的真实歌曲（LLM 有搜索结果但没用）
      2. 从 runtime_dj_state.playlist_queue 取第一首（队列中还有歌）
      3. 使用硬编码 fallback 列表（极端兜底 — 至少能放一首）
    """
    # 第 1 级：工具搜索结果
    real = _get_real_search_result(state)
    if real:
        return real

    # 第 2 级：队列中还有歌（可能队列消费未完全同步）
    rds = state.get("dependencies", {}).get("runtime_dj_state")
    if rds:
        queue = rds.get("playlist_queue", []) or []
        if queue:
            return queue[0]

    # 第 3 级：硬编码兜底
    import random
    return dict(random.choice(_REAL_FALLBACK_SONGS))


def _is_fake_song_id(song_id: str) -> bool:
    """检查 song_id 是否为虚假/编造 ID。

    真实网易云 song_id 是纯数字字符串。
    虚假 ID 特征：default_ 前缀 / mock_ 前缀 / 非纯数字。
    """
    if not song_id:
        return True
    if song_id.startswith(("default_", "mock_")):
        return True
    if not song_id.isdigit():
        return True
    return False


def _fill_queue_with_fallback(state: dict, current_song_id: str):
    """用 _REAL_FALLBACK_SONGS 填充 playlist_queue（排除当前歌曲）。"""
    queue_songs = [s for s in _REAL_FALLBACK_SONGS if s["song_id"] != current_song_id]
    if not queue_songs:
        return
    rds = state.get("dependencies", {}).get("runtime_dj_state")
    if not rds:
        return
    final_queue = _to_queue_songs(queue_songs)
    rds["playlist_queue"] = final_queue
    state_manager.player.update_player_event({
        "subtype": "playlist_changed",
        "playlist": final_queue,
        "strategy": {"source": "fallback"},
    })
    logger.info("_fill_queue_with_fallback: filled queue with %d songs", len(final_queue))


def _to_frontend_song(raw: dict) -> dict:
    """将内部 song dict 转为前端 WS music.play 格式。"""
    return {
        "id": raw.get("song_id") or raw.get("id", ""),
        "name": raw.get("name", "未知歌曲"),
        "artists": raw.get("artists") or (
            [{"id": "", "name": raw["artist"]}] if raw.get("artist") else []
        ),
        "album": raw.get("album") if isinstance(raw.get("album"), dict) else {
            "id": "", "name": raw.get("album", ""),
        },
        "cover_url": raw.get("cover_url", ""),
        "duration_ms": raw.get("duration_ms", 0),
        "fee": raw.get("fee", 0),
    }


def _to_queue_songs(songs: list[dict]) -> list[dict]:
    """将 LLM playlist 剩余歌曲转为 playlist_queue 格式（精简字段）。"""
    result = []
    for s in songs:
        result.append({
            "song_id": s.get("id") or s.get("song_id", ""),
            "name": s.get("name", "未知歌曲"),
            "artist": s.get("artist", ""),
            "cover_url": s.get("cover_url", ""),
            "duration_ms": s.get("duration_ms", 0),
        })
    return result


def _generate_transition_speech(snapshot: dict, program: dict) -> str:
    """根据 program_mood + today_theme 生成过渡语。

    ★ v0.1.2 P1-5：3 档模板 + fallback（按 ProgramMood 枚举值）。
    不调用 LLM，纯规则模板。
    """
    theme = program.get("today_theme", "今晚")
    mood = snapshot.get("program_mood", ProgramMood.NEUTRAL.value)

    if mood == ProgramMood.ENERGETIC.value:
        return f"{theme}的节奏告一段落，下一段旅程准备好了吗？"
    elif mood == ProgramMood.WARM.value:
        return f"{theme}的歌都听完了，让我为你找一些更贴心的..."
    elif mood == ProgramMood.REFLECTIVE.value:
        return f"{theme}的小曲停下片刻，听听你心里的声音..."
    else:
        # fallback（含 NEUTRAL 和未知 mood 兜底）
        return f"{theme}的播放列表告一段落，让我重新为你规划一下..."
