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
from agent.services.song_resolver import normalize_song_name, pick_best_song, dedup_candidates

logger = logging.getLogger(__name__)

# ★ 兜底 fallback 歌曲（极端情况使用，source=fallback 标记不进入正常队列）
#   v9.1 原则：正常队列永远只包含 source="search" 的歌曲，
#   fallback 歌曲只能在搜索全部失败时作为最后保护，且被标记以供后续 REPLAN 替换。
_REAL_FALLBACK_SONGS = [
    {"song_id": "108914", "name": "江南", "artist": "林俊杰", "source": "fallback"},
    {"song_id": "25642214", "name": "爱错(Live)", "artist": "王力宏", "source": "fallback"},
    {"song_id": "26548584", "name": "Happy", "artist": "Pharrell Williams", "source": "fallback"},
    {"song_id": "28403111", "name": "特别的人", "artist": "方大同", "source": "fallback"},
    {"song_id": "3339230677", "name": "晴天", "artist": "周杰伦", "source": "fallback"},
    {"song_id": "4336330", "name": "Here Comes The Sun", "artist": "The Beatles", "source": "fallback"},
]

# ★ playlist_queue 低水位阈值：队列剩余 ≤ 3 首时触发后台 REPLAN 补充
_PLAYLIST_LOW_WATERMARK = 3

# ★ v9.13: INIT 节目单长度约束
INIT_MIN_QUEUE_SIZE = 6  # 队列低于此值时不会播放，触发 REPLAN


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

	# ★ dj_monologue — 透传 dj_host 生成的 dj_speech + 添加 tts_speak action
	if trigger_type == TriggerType.DJ_MONOLOGUE.value:
		return await _handle_dj_monologue(state)

	# 其他（system / user_control）— 非本 spec 范围，返回空
	return {
		"actions": [],
		"pending_payload": None,
		"should_speak": False,
		"should_play_music": False,
	}


async def _handle_init_plan(state: dict, init_plan: dict) -> dict:
	"""处理 init_plan：应用 ProgramState + 构建初始队列 + 播放第一首。

	★ Q14+15 事务顺序（用户拍板）：
	  ① _build_init_queue（逐首解析 LLM 规划歌曲到 playlist_queue）
	  ② save_program_state
	  ③ INIT_MIN_QUEUE_SIZE 守卫（不足 8 首 → 推 REPLAN，不播放）
	  ④ play_music（播第一首）
	  ⑤ emit status.welcome
	  ⑥ emit chat.reply
	  ⑦ emit music.play

	★ v9.13：队列构建方式改为"LLM 规划 → 逐首 tool 搜索 → 逐首 pick_best_song"，
	  不再使用 _get_all_search_songs + dedup 混搜结果作为歌单。
	  每首歌独立解析为最佳版本，队列内容 = LLM 规划的节目单。
	"""
	program_state = init_plan.get("program_state", {})
	initial_playlist = init_plan.get("initial_playlist", [])
	welcome_text = init_plan.get("welcome_text", "")
	tool_msgs = state.get("tool_messages", []) or []

	# ★ v9.13: 构建初始队列 — 对 LLM 规划的每首歌逐一 pick_best_song
	#   不再使用 _get_all_search_songs + dedup 混搜结果作为歌单。
	init_queue = _build_init_queue(initial_playlist, tool_msgs)
	logger.info("Init queue: built %d songs from %d LLM-planned songs (min=%d)",
	            len(init_queue), len(initial_playlist), INIT_MIN_QUEUE_SIZE)

	# ① 写入 program_state.json + 同步 RuntimeDJState
	save_ok = state_manager.program.save_program_state(program_state)
	if save_ok:
		rds = state.get("dependencies", {}).get("runtime_dj_state")
		if rds is not None:
			sync_from_program_state(rds, program_state)

	# ★ v9.13: INIT 队列长度守卫
	#   条件 1：队列完全为空 → 极端兜底，不播放
	#   条件 2：LLM 规划了 ≥6 首但解析不足 → 触发 REPLAN 重新规划
	#   若 LLM 本身规划未达阈值（测试 mock 等场景），则正常播放已有歌曲。
	if not init_queue:
		logger.warning("Init queue is empty, cannot play anything")
		rds = state.get("dependencies", {}).get("runtime_dj_state")
		if rds:
			rds["playlist_queue"] = []
		now_ts = int(time.time() * 1000)
		return {
			"actions": [],
			"pending_payload": {
				"chat_reply": "我正在准备节目单，请稍等片刻……",
				"status_update": {
					"type": "welcome",
					"init_mode": state.get("init_mode", "first_init"),
					"program_state": program_state,
					"ts": now_ts,
				},
			},
			"should_speak": True,
			"should_play_music": False,
		}

	needs_replan = (len(initial_playlist) >= INIT_MIN_QUEUE_SIZE
	                and len(init_queue) < INIT_MIN_QUEUE_SIZE)
	if needs_replan:
		logger.warning("Init queue too small: %d < %d, triggering REPLAN instead of playing",
		               len(init_queue), INIT_MIN_QUEUE_SIZE)
		rds = state.get("dependencies", {}).get("runtime_dj_state")
		if rds:
			rds["playlist_queue"] = []
		refs = state.get("__refs__") or {}
		event_svc = refs.get("event_service")
		if event_svc is not None:
			await event_svc.push_replan(f"init_queue_too_small:{len(init_queue)}")
		now_ts = int(time.time() * 1000)
		return {
			"actions": [],
			"pending_payload": {
				"chat_reply": "我正在准备今晚的节目单，请稍等片刻……",
				"status_update": {
					"type": "welcome",
					"init_mode": state.get("init_mode", "first_init"),
					"program_state": program_state,
					"ts": now_ts,
				},
			},
			"should_speak": True,
			"should_play_music": False,
		}

	# 队列足够 → 播第一首 + 存储队列
	first_song = init_queue[0]
	first_song_id = first_song["song_id"]
	now_ts = int(time.time() * 1000)

	rds = state.get("dependencies", {}).get("runtime_dj_state")
	if rds:
		rds["playlist_queue"] = init_queue  # INIT = replace
		state_manager.player.update_player_event({
			"subtype": "playlist_changed",
			"playlist": init_queue,
			"strategy": {"source": "init_plan"},
		})
		logger.info("Init: stored %d songs in playlist_queue (per-song resolved)", len(init_queue))

	# 构造 actions
	actions = [{
		"type": "play_song",
		"params": {"song_id": first_song_id, "auto_play": True},
		"reason": "init_plan_first_song",
	}]

	# 转为前端 Song 格式
	ws_song = _to_frontend_song(first_song)

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
		"should_play_music": True,
	}


async def _handle_song_finished(state: dict) -> dict:
	"""处理 song_finished / play_end / user_skip 事件。

	★ v0.6 D 项 + ★ v0.1.1 E 项 + ★ v0.1.2 P1-5：
	- queue 有下一首 → play_song(next)，不写 feedback
	- queue 空 → transition speech + 推 REPLAN_REQUEST

	★ P0-2: RDS current_song 与 finished song 不同时跳过（chat_send 已修改节目状态）
	★ P0-3: 从 live RDS 读队列，不用事件快照
	"""
	rds = state.get("dependencies", {}).get("runtime_dj_state")

	# ★ P0-2: 检测队列分歧
	#   当 pending_user_interrupt=True（用户刚发了聊天），跳过 play_end 自动推进，
	#   因为 chat_send 已修改了 RDS（如 insert_now），当前 play_end 已过时。
	#   当 pending_user_interrupt=False，分歧是时序竞争（前端 auto-advance 先于
	#   play_end 被处理），应正常自动推进。
	trigger_event = state.get("trigger_event") or {}
	finished_id = trigger_event.get("song_id", "")
	current_song = (rds.get("current_song") or {}) if rds else {}
	current_id = current_song.get("song_id", "")
	if finished_id and current_id and finished_id != current_id:
		if rds and rds.get("pending_user_interrupt"):
			rds["pending_user_interrupt"] = False
			logger.info("play_end skipped: RDS current=%s diverged from finished=%s "
			            "(pending_user_interrupt, queue modified by chat)",
			            current_id, finished_id)
			return {
				"actions": [],
				"pending_payload": None,
				"should_speak": False,
				"should_play_music": False,
				"feedback_record": None,
			}
		# No pending_user_interrupt → timing race (frontend auto-advanced before
		# backend processed play_end). Proceed with normal auto-advance.
		logger.info("play_end divergence but no pending_user_interrupt, "
		            "proceeding with auto-advance (timing race current=%s finished=%s)",
		            current_id, finished_id)

	# ★ P0-3: 从 live RDS 读队列（不是事件快照）
	playlist_queue = (rds.get("playlist_queue") or []) if rds else []
	program = state.get("program") or {}
	next_song = playlist_queue[0] if playlist_queue else None

	if next_song:
		song_id = next_song.get("song_id") or next_song.get("id", "")
		ws_song = _to_frontend_song(next_song)

		# ★ 歌间过渡语（不论 rds 是否存在都可用）
		song_name = next_song.get("name", "下一首")
		transition_text = f"接下来继续听「{song_name}」。"

		# ★ 低水位标记：队列消费后 ≤3 → 后台 REPLAN + DJ 说话
		is_low_watermark = False

		# ★ 消费队列：移除已播放的歌曲（更新 live RDS + mirror）
		if rds and rds.get("playlist_queue"):
			rds["playlist_queue"] = rds["playlist_queue"][1:]
			remaining = len(rds["playlist_queue"])
			state_manager.player.update_player_event({
				"subtype": "playlist_changed",
				"playlist": rds["playlist_queue"],
				"strategy": rds.get("queue_strategy", {}),
			})
			logger.info("Consumed playlist_queue, %d songs remaining", remaining)

			# ★ v9.1: Low watermark — queue ≤ N → 后台触发 REPLAN（不中断播放）
			if remaining <= _PLAYLIST_LOW_WATERMARK:
				is_low_watermark = True
				refs = state.get("__refs__") or {}
				event_svc = refs.get("event_service")
				if event_svc is not None:
					await event_svc.push_replan(f"low_watermark:{remaining}")
					logger.info("Low watermark: queue=%d, pushed background REPLAN_REQUEST",
					            remaining)

			# ★ 若 DJ Host 已通过 song_progress 生成话术，跳过简单过渡语
			finished_song = current_song  # 从 live RDS 读
			finished_id = finished_song.get("song_id") or finished_song.get("id", "")
			dj_done = (
				rds.get("last_dj_speech_song_id") == finished_id
				and rds.get("last_dj_speech_at_ms", 0) > 0
			) if rds else False

			if dj_done:
				transition_text = ""

			# ★ 低水位时覆盖过渡语：提到正在找新歌（仅在 DJ 未说话时）
			if not dj_done and is_low_watermark:
				transition_text = f"{song_name}，这首先听着，我再去找些更合适的。"

		# ★ should_speak：只在低水位时有意义的过渡语场景才说话
		should_speak = bool(transition_text) and is_low_watermark

		return {
			"actions": [{
				"type": "play_song",
				"params": {"song_id": song_id, "auto_play": True},
				"reason": "song_finished_queue_next",
			}],
			"pending_payload": {
				"music_play": {"song": ws_song, "auto_play": True},
				"chat_reply": transition_text,
			},
			"should_play_music": True,
			"should_speak": should_speak,
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

	# ★ 优先用 DJ Host 生成话术（LLM → 模板 fallback）
	transition_text = ""
	dj_host = refs.get("dj_host_service")
	if dj_host:
		env = state.get("environment") or {}
		user = state.get("user") or {}
		dj_context = {
			"persona_name": "Soul",
			"persona_style": "warm",
			"target_song_id": "",
			"current_song": (rds.get("current_song") if rds else None),
			"next_song": None,
			"queue_empty": True,
			"program_mood": (rds.get("program_mood", "neutral") if rds else "neutral"),
			"today_theme": program.get("today_theme", "今晚"),
			"day_period": env.get("day_period", "unknown"),
			"user_nickname": user.get("nickname", ""),
			"user_mood": env.get("user_mood", ""),
		}
		try:
			transition_text = await dj_host.generate_speech(dj_context)
		except Exception as e:
			logger.warning("DJ Host inline error: %s", e)
			transition_text = ""

	if not transition_text:
		transition_text = _generate_transition_speech(rds or {}, program)

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
				"mood": (rds or {}).get("program_mood", "neutral"),
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


async def _handle_dj_monologue(state: dict) -> dict:
	"""处理 dj_monologue 事件：透传 dj_host 的 dj_speech + 添加 tts_speak action。

	数据流：
	  dj_host 生成 dj_speech 到 pending_payload
	  → action_planner 透传 + 加 TTS action
	  → action_executor 执行 TTS
	  → emit_response 发 dj.speech + tts.synthesize
	"""
	pending = state.get("pending_payload") or {}

	# 获取 dj_host 生成的话术
	dj_speech = pending.get("dj_speech") or {}
	text = dj_speech.get("text", "")

	if not text:
		logger.debug("dj_monologue: no dj_speech text, skip")
		return {"actions": [], "pending_payload": None, "should_speak": False, "should_play_music": False}

	actions = [{"type": "tts_speak", "params": {"text": text}, "reason": "dj_monologue"}]

	logger.info("dj_monologue: pass-through with TTS action (%d chars)", len(text))
	return {
		"actions": actions,
		"pending_payload": pending,
		"should_speak": True,
		"should_play_music": pending.get("music_play") is not None,
	}


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

	# ★ 当 LLM 调用失败（decision={}）且是用户发消息触发的 → fallback 回话
	#   不沉默：至少让用户知道系统在工作
	trigger = state.get("trigger_type", "")
	if not decision and trigger == "conversation":
		should_speak = True
		text = "嗯，我听到了。让我看看接下来给你放点什么音乐。"
		dialogue["should_speak"] = True
		dialogue["text"] = text
		dialogue["style"] = "warm"
		decision["dialogue_decision"] = dialogue
		logger.info("ActionPlanner: LLM returned empty decision, using fallback chat_reply")

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

	# ★ v9.2.1: 队列更新策略尊重 LLM action，不再按 trigger_type 覆盖
	#   insert_now → 即时插播（点名歌曲插到队列头部，不污染队列）
	#   replace → 用户要求换节目
	#   append/add → 补充到队列尾部
	#   keep → 不做改变
	trigger = state.get("trigger_type", "")
	trigger_event = state.get("trigger_event", {}) or {}
	user_text = (trigger_event.get("text", "") or "").strip()
	replan_reason = (trigger_event.get("reason", "") or "")

	if playlist_action in ("replace", "add", "append", "insert_now", "keep"):
		queue_update = playlist_action
	elif trigger in ("replan_event", "timer_event"):
		queue_update = "append"
	elif trigger == "conversation" and user_text:
		queue_update = "append"  # 默认追加而非替换
	else:
		queue_update = "keep"

	logger.info("Queue strategy: trigger=%s user_text=%r playlist_action=%s → queue_update=%s",
	            trigger, user_text[:20] if user_text else "", playlist_action, queue_update)

	# ★ v9.2.1: insert_now/append 也进入歌曲解析流程
	if playlist_action in ("replace", "add", "append", "insert_now") and songs:
		name = songs[0].get("name", "")
		artist = songs[0].get("artist", "")
		tool_msgs = state.get("tool_messages", []) or []

		# ★ Song Resolver：从搜索结果中选出最佳版本
		#   pick_best_song 按歌名匹配度 + 歌手匹配度 + 版本分数综合评分
		#   优先级：原版 > 录音室 > Live > 翻唱 > 伴奏
		current_search = _get_current_search_songs(tool_msgs)
		best = pick_best_song(name, artist, current_search)
		song = None
		song_id = ""

		if best:
			song = best
			song_id = best.get("id", "")
			logger.info("ActionPlanner: pick_best_song name=%r artist=%r -> song_id=%s",
			            name, artist, song_id)
		else:
			# 兜底：用第一条搜索结果
			first_search = _get_first_search_song(tool_msgs)
			if first_search:
				song = first_search
				song_id = first_search.get("id", "")
				logger.info("ActionPlanner: using first search result id=%s (pick_best_song unmatched)",
				            song_id, name)
			else:
				# 兜底：匹配 fallback
				fallback = _match_fallback_by_name_artist(name, artist)
				if fallback:
					song = fallback
					song_id = fallback["song_id"]
					logger.info("ActionPlanner: fallback match name=%r artist=%r -> song_id=%s",
					            name, artist, song_id)
				else:
					logger.warning("ActionPlanner: no match for name=%r artist=%r",
					               name, artist)

		# ★ 边界保护（最后防线）
		if song_id and _is_fake_song_id(song_id):
			logger.warning("ActionPlanner: rejecting fake song_id=%s after resolution", song_id)
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

			# ★ v9.1 队列填充：Song Resolver 去重后入队
			#   1. 只使用当前 tool loop 搜索结果（_get_current_search_songs）
			#   2. dedup_candidates 去重（归一化歌名 + 歌手）
			#   3. append 时对现有队列去重；replace 时候选自身去重
			# ★ v9.2.1: insert_now 只插入点名歌曲，不添加搜索结果
			rds = state.get("dependencies", {}).get("runtime_dj_state")
			current_search = _get_current_search_songs(tool_msgs)

			if rds:
				# ★ RDS current_song 也加入队列排除列表，防止 auto-advance 播放同一首歌
				_rds_current = (rds.get("current_song") or {})
				_rds_exclude = []
				if _rds_current.get("song_id"):
					_rds_exclude = [{
						"song_id": _rds_current["song_id"],
						"name": _rds_current.get("name", ""),
					}]

				if queue_update == "insert_now":
					# ★ v9.2.1: 即时插播 — 只把点名的歌插入队列头部
					existing = rds.get("playlist_queue", []) or []
					insert_item = {
						"song_id": song_id,
						"name": name or (song or {}).get("name", "未知歌曲"),
						"artist": artist or (
							", ".join(a.get("name", "") for a in ((song or {}).get("artists", []) or []))
						) or (song or {}).get("artist", ""),
						"cover_url": (song or {}).get("cover_url", ""),
						"duration_ms": (song or {}).get("duration_ms", 0),
						"source": "search",
					}
					# 避免队列头部重复
					is_dup = any(
						q.get("song_id") == song_id or (
							q.get("name") == insert_item["name"]
							and q.get("artist") == insert_item["artist"]
						)
						for q in existing[:1]  # 只检查队首
					)
					if not is_dup:
						rds["playlist_queue"] = [insert_item] + existing
					else:
						rds["playlist_queue"] = existing
					logger.info("Queue insert_now: song=%s at front, total=%d songs (dup=%s)",
					            song_id, len(rds["playlist_queue"]), is_dup)
				elif queue_update in ("add", "append"):
					existing = rds.get("playlist_queue", []) or []
					_dedup_existing = existing + _rds_exclude if _rds_exclude else existing
					filtered = dedup_candidates(current_search, _dedup_existing, current_song_id=song_id) if current_search else []
				else:
					# replace：对候选自身去重（不同版本），现有队列被替换
					#   _rds_exclude 防止当前 RDS 歌曲进入新队列（auto-advance 不会切回同一首）
					_dedup_existing = _rds_exclude if _rds_exclude else None
					filtered = dedup_candidates(current_search, existing_queue=_dedup_existing, current_song_id=song_id) if current_search else []
					existing = []

				if queue_update != "insert_now":
					if current_search:
						queue_items = []
						for s in filtered:
							sid = s.get("id", "") or s.get("song_id", "")
							if sid and not _is_fake_song_id(sid):
								queue_items.append({
									"song_id": sid,
									"name": s.get("name", "未知歌曲"),
									"artist": ", ".join(
										a.get("name", "") for a in (s.get("artists", []) or [])
									) or s.get("artist", ""),
									"source": "search",
								})

						final_queue = _to_queue_songs(queue_items)
						rds["playlist_queue"] = existing + final_queue
						logger.info("Queue %s: %d + %d = %d songs (filtered from %d candidates)",
						            queue_update, len(existing), len(final_queue),
						            len(existing) + len(final_queue), len(current_search))
					else:
						logger.info("Queue: no current search results, queue stays unchanged")

				state_manager.player.update_player_event({
					"subtype": "playlist_changed",
					"playlist": rds["playlist_queue"],
					"strategy": {"source": "llm_decision", "action": playlist_action},
				})
		elif should_speak:
			# song_id 被拒，但 LLM 计划了说话 → 把 fallback 信息加进 dialogue
			fallback_text = (
				f"{text.rstrip('。')}，不过我没有找到可播放的歌曲，"
				"让我重新搜索一下。"
			) if text else "我没有找到可播放的歌曲，正在重新搜索..."
			pending_payload["chat_reply"] = fallback_text

	# ★ LLM 输出 add/replace 但 songs=0 → 尝试从工具搜索结果或硬编码兜底中提取歌曲
	#   （场景：REPLAN 搜索后 LLM 仍认为无歌 / 搜索返回空）
	if playlist_action in ("replace", "add", "insert_now") and not pending_payload.get("music_play"):
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
				_fill_queue_from_search_or_fallback(state, song_id, state.get("tool_messages", []) or [])
				logger.info("ActionPlanner: fallback play song_id=%s (LLM output 0 songs)", song_id)

	# ★ LLM 输出 keep + songs=0 → 队列有歌则不干预，队列空时兜底
	#   v9.5 fix: keep 语义是"保持现有队列"，队列已有歌时不应强行切歌
	if playlist_action == "keep" and not songs and not pending_payload.get("music_play"):
		rds = state.get("dependencies", {}).get("runtime_dj_state")
		existing_queue = (rds.get("playlist_queue", []) or []) if rds else []
		if existing_queue:
			logger.info("ActionPlanner: LLM keep + queue has %d songs, no fallback needed",
			            len(existing_queue))
		else:
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
					_fill_queue_from_search_or_fallback(state, song_id, state.get("tool_messages", []) or [])
					logger.info("ActionPlanner: fallback play song_id=%s (LLM keep + queue empty)", song_id)

	# ★ RESUME 安全网：LLM 无 play_song action，但队列有歌、无 current_song → 自动播放第一首
	#   场景：RESUME 模式 LLM 见队列非空 + "已暂停" → action=keep/空 songs → 无 play_song
	#   此时队列有歌但 nothing playing，需自动恢复播放。
	if not pending_payload.get("music_play") and not any(a.get("type") == "play_song" for a in actions):
		_safe_rds = state.get("dependencies", {}).get("runtime_dj_state")
		_snap = state.get("runtime_snapshot") or {}
		_current = _snap.get("current_song") or (_safe_rds.get("current_song") if _safe_rds else None)
		_queue = (_safe_rds.get("playlist_queue", []) or []) if _safe_rds else []
		if _queue and not _current:
			_first = _queue[0]
			_sid = _first.get("song_id") or _first.get("id", "")
			if _sid and not _is_fake_song_id(_sid):
				actions.append({
					"type": "play_song",
					"params": {"song_id": _sid, "auto_play": True},
					"reason": "resume_queue_first",
				})
				pending_payload["music_play"] = {
					"song": _to_frontend_song(_first),
					"auto_play": True,
				}
				logger.info("ActionPlanner: resume play first queue song=%s (no current_song, queue has %d songs)",
				            _sid, len(_queue))

	# ★ P0-2: 用户中断已消费 — 清除标记，后续 play_end 可正常推进
	_rds_for_clear = state.get("dependencies", {}).get("runtime_dj_state")
	if _rds_for_clear and _rds_for_clear.get("pending_user_interrupt"):
		_rds_for_clear["pending_user_interrupt"] = False
		logger.debug("pending_user_interrupt cleared after LLM decision")

	return {
		"actions": actions,
		"pending_payload": pending_payload if pending_payload else None,
		"should_speak": should_speak,
		"should_play_music": bool(pending_payload.get("music_play")),
	}


def _resolve_song_from_tools(name: str, artist: str, tool_messages: list) -> dict | None:
	"""[向后兼容] 委托 pick_best_song 从搜索结果中选最佳歌曲。

	已被 Song Resolver pick_best_song 取代，保留作为测试兼容入口。
	"""
	from agent.services.song_resolver import pick_best_song as _pick_best

	all_songs = _get_all_search_songs(tool_messages)
	return _pick_best(name, artist, all_songs)


def _match_fallback_by_name_artist(name: str, artist: str) -> dict | None:
	"""按 name+artist 匹配 _REAL_FALLBACK_SONGS 列表。

	当工具搜索结果为空时，尝试从硬编码 fallback 列表匹配。
	"""
	if not name and not artist:
		return None

	name_lower = name.lower().strip()
	artist_lower = artist.lower().strip()

	for song in _REAL_FALLBACK_SONGS:
		sname = song["name"].lower().strip()
		sartist = song["artist"].lower().strip()

		name_ok = not name_lower or (name_lower in sname or sname in name_lower)
		artist_ok = not artist_lower or (artist_lower in sartist or sartist in artist_lower)

		if name_ok and artist_ok:
			return dict(song)
	return None


def _get_all_search_songs(tool_messages: list) -> list[dict]:
	"""从所有 play_music 搜索结果中提取全部歌曲（去重，按搜索顺序）。

	每次 play_music 调用返回最多 5 首，多次搜索叠加。
	用于队列填充：REPLAN 搜索到的歌曲全部入队，实现滚动更新。
	"""
	seen = set()
	result = []
	for msg in reversed(tool_messages):
		if msg.get("name") != "play_music":
			continue
		res = msg.get("result", {})
		if not isinstance(res, dict):
			continue
		songs = res.get("songs", [])
		for s in songs:
			sid = s.get("id", "") or s.get("song_id", "")
			if sid and sid not in seen and not _is_fake_song_id(sid):
				seen.add(sid)
				result.append(s)
	return result


def _get_current_search_songs(tool_messages: list, max_recent: int = 3) -> list[dict]:
	"""只读取最近一次 tool loop 的搜索结果（最多 max_recent 次 play_music 调用）。

	与 _get_all_search_songs 的区别：
	- 只读最近 N 次 play_music 调用，而非全部历史
	- 防止跨 REPLAN 周期搜索结果累积
	"""
	seen = set()
	result = []
	count = 0
	for msg in reversed(tool_messages):
		if msg.get("name") != "play_music":
			continue
		count += 1
		if count > max_recent:
			break
		res = msg.get("result", {})
		if not isinstance(res, dict):
			continue
		songs = res.get("songs", [])
		for s in songs:
			sid = s.get("id", "") or s.get("song_id", "")
			if sid and sid not in seen and not _is_fake_song_id(sid):
				seen.add(sid)
				result.append(s)
	return result


def _get_first_search_song(tool_messages: list) -> dict | None:
	"""从 tool_messages 获取第一条搜索结果（优先最新 tool loop）。"""
	all_songs = _get_current_search_songs(tool_messages)
	return all_songs[0] if all_songs else None


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


def _fill_queue_from_search_or_fallback(state: dict, current_song_id: str, tool_messages: list):
	"""用搜索结果 + fallback 填充 playlist_queue（紧急兜底路径）。

	v9.1（Song Resolver 版）：
	- 只使用当前 tool loop 搜索结果（_get_current_search_songs）
	- dedup_candidates 对现有队列去重
	- 搜索结果为空时，用 _REAL_FALLBACK_SONGS 标记 source="fallback" 补满
	- 总是 append 到现有队列尾部（不替换）
	"""
	rds = state.get("dependencies", {}).get("runtime_dj_state")
	if not rds:
		return

	existing = rds.get("playlist_queue", []) or []

	# 优先级 1: 搜索结果（仅当前 tool loop）
	current_search = _get_current_search_songs(tool_messages)
	filtered = dedup_candidates(current_search, existing, current_song_id=current_song_id)

	candidates = []
	if filtered:
		for s in filtered:
			sid = s.get("id", "") or s.get("song_id", "")
			if sid and not _is_fake_song_id(sid):
				candidates.append({
					"song_id": sid,
					"name": s.get("name", "未知歌曲"),
					"artist": ", ".join(
						a.get("name", "") for a in (s.get("artists", []) or [])
					) or s.get("artist", ""),
					"source": "search",
				})

	# 优先级 2: 搜索结果为空 → 用 fallback 补满（source="fallback"）
	if not candidates:
		existing_ids = set(s.get("song_id", "") for s in existing)
		for fs in _REAL_FALLBACK_SONGS:
			if fs["song_id"] != current_song_id and fs["song_id"] not in existing_ids:
				candidates.append({
					"song_id": fs["song_id"],
					"name": fs["name"],
					"artist": fs["artist"],
					"source": "fallback",
				})
			if len(candidates) >= 5:
				break

	final_queue = _to_queue_songs(candidates[:10])
	# 紧急兜底 = append（不替换现有队列）
	rds["playlist_queue"] = existing + final_queue
	state_manager.player.update_player_event({
		"subtype": "playlist_changed",
		"playlist": rds["playlist_queue"],
		"strategy": {"source": "search_or_fallback", "action": "append"},
	})
	logger.info("_fill_queue_from_search_or_fallback: %d songs appended (%d search, %d fallback, existing=%d)",
	            len(final_queue),
	            len([s for s in candidates if s.get("source") == "search"]),
	            len([s for s in candidates if s.get("source") == "fallback"]),
	            len(existing))


def _build_init_queue(initial_playlist: list, tool_messages: list) -> list[dict]:
    """对 LLM 规划歌曲逐首 pick_best_song，去重后形成初始队列。

    ★ v9.13: LLM 生成 -> tool 逐首搜索 -> resolver 逐首解析
    不再使用 _get_all_search_songs + dedup_candidates 混搜歌单方案。

    去重：同名（归一化）只留一首，同 song_id 只留一首。
    """
    all_search = _get_all_search_songs(tool_messages)
    seen_names: set[str] = set()
    seen_ids: set[str] = set()
    queue: list[dict] = []

    for song in initial_playlist:
        name = song.get("name", "")
        artist = song.get("artist", "")
        if not name:
            continue

        best = pick_best_song(name, artist, all_search)
        if not best:
            logger.info("Init queue: pick_best_song unmatched for %r %r, skip", name, artist)
            continue

        sid = best.get("id", "") or best.get("song_id", "")
        if not sid or _is_fake_song_id(sid):
            continue

        nname = normalize_song_name(name)
        if nname and nname in seen_names:
            logger.debug("Init queue: dedup skip %r (same song already in queue)", name)
            continue
        if sid and sid in seen_ids:
            continue

        if nname:
            seen_names.add(nname)
        if sid:
            seen_ids.add(sid)

        queue.append({
            "song_id": sid,
            "name": best.get("name", name),
            "artist": ", ".join(
                a.get("name", "") for a in (best.get("artists", []) or [])
            ) or best.get("artist", artist),
            "cover_url": best.get("cover_url", ""),
            "duration_ms": best.get("duration_ms", 0),
            "source": "search",
        })

    logger.info("_build_init_queue: %d songs from %d LLM songs (%d named, %d search candidates)",
                len(queue), len(initial_playlist), len(seen_names), len(all_search))
    return queue


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
	"""将歌曲列表转为 playlist_queue 格式（精简字段）。"""
	result = []
	for s in songs:
		result.append({
			"song_id": s.get("id") or s.get("song_id", ""),
			"name": s.get("name", "未知歌曲"),
			"artist": s.get("artist", ""),
			"cover_url": s.get("cover_url", ""),
			"duration_ms": s.get("duration_ms", 0),
			"source": s.get("source", "search"),
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
