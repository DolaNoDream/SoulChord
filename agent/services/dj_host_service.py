"""DJHostService — LLM 驱动的 DJ 话术生成服务，4 层 fallback。

Layer 1: Cache（绑定 target_song_id + expire_at）
Layer 2: Inline LLM（10s timeout）
Layer 3: Template（保留原始 _generate_transition_speech 逻辑）
Layer 4: Silent（返回空字符串）

Layer 1-2 需要 DJ Host enabled。Layer 3-4 始终可用。
"""

import asyncio
import logging
import time

from agent.prompts.dj_speech_prompt import format_dj_speech_prompt

logger = logging.getLogger(__name__)


class DJHostService:
    """DJ 话术生成服务。4 层 fallback 链生产过渡语文本。"""

    def __init__(
        self,
        llm_service=None,
        *,
        enabled: bool = True,
        cache_ttl_s: int = 300,
        llm_timeout_s: int = 10,
        persona_name: str = "Soul",
        persona_style: str = "warm",
    ):
        self._llm = llm_service
        self._enabled = enabled
        self._cache_ttl_s = cache_ttl_s
        self._llm_timeout_s = llm_timeout_s
        self._persona_name = persona_name
        self._persona_style = persona_style
        # cache: { "dj_speech:{song_id}": {"text": str, "expire_at": float} }
        self._cache: dict[str, dict] = {}

    async def generate_speech(self, context: dict) -> str:
        """生成 DJ 话术，4 层 fallback。

        Args:
            context: 包含 current_song/next_song/program_mood/today_theme
                     等段的上下文字典。必须包含 target_song_id 用于 cache 绑定。

        Returns:
            str: 生成的话术文本，"" 表示静默。
        """
        target_song_id = context.get("target_song_id", "")

        # Layer 1: Cache
        cached = self._check_cache(target_song_id)
        if cached is not None:
            logger.debug("DJ Host: L1 cache hit for song_id=%s", target_song_id)
            return cached

        # Layer 2-4: 需要 enabled + LLM client
        if not self._enabled or self._llm is None:
            text = self._generate_template(context)
            if text:
                self._set_cache(target_song_id, text)
            return text

        # Layer 2: Inline LLM (10s timeout)
        try:
            prompt = format_dj_speech_prompt(context)
            text = await asyncio.wait_for(
                self._call_llm(prompt),
                timeout=self._llm_timeout_s,
            )
            if text:
                self._set_cache(target_song_id, text)
                return text
        except asyncio.TimeoutError:
            logger.warning("DJ Host: L2 LLM timeout (%ss), fallback to L3", self._llm_timeout_s)
        except Exception as e:
            logger.warning("DJ Host: L2 LLM error: %s, fallback to L3", e)

        # Layer 3: Template
        text = self._generate_template(context)
        if text:
            self._set_cache(target_song_id, text)
            return text

        # Layer 4: Silent
        logger.info("DJ Host: all 4 layers exhausted, silent fallback")
        return ""

    # ── Cache ──

    def _check_cache(self, song_id: str) -> str | None:
        if not song_id:
            return None
        key = f"dj_speech:{song_id}"
        entry = self._cache.get(key)
        if entry and entry["expire_at"] > time.time():
            return entry["text"]
        return None

    def _set_cache(self, song_id: str, text: str):
        if not song_id:
            return
        key = f"dj_speech:{song_id}"
        self._cache[key] = {
            "text": text,
            "expire_at": time.time() + self._cache_ttl_s,
        }

    def invalidate_cache(self, song_id: str):
        """强制失效缓存（用户反馈 like/dislike 后调用）。"""
        self._cache.pop(f"dj_speech:{song_id}", None)

    # ── LLM ──

    async def _call_llm(self, prompt: str) -> str:
        """调 LLM 并提取 text 字段。"""
        result = await self._llm.call_json(prompt)
        if result.get("ok") and result.get("data"):
            data = result["data"]
            if data.get("should_speak", False) and data.get("text"):
                return data["text"].strip()
        return ""

    # ── Template (Layer 3) ──

    def _generate_template(self, context: dict) -> str:
        """模板层 fallback。聚焦当前歌曲，不提前介绍下一首。"""
        mood = context.get("program_mood", "neutral")
        theme = context.get("today_theme", "今晚")
        current_song = context.get("current_song") or {}
        song_name = current_song.get("name", "")

        if song_name:
            if mood == "energetic":
                return f"来听{song_name}，让{theme}的节奏继续燃烧！"
            elif mood == "warm":
                return f"送上这首{song_name}，愿{theme}温暖你的心。"
            elif mood == "reflective":
                return f"静静听这首{song_name}，让思绪随{theme}的旋律飘荡..."
            else:
                return f"继续播放「{song_name}」，享受{theme}的时光。"
        else:
            # 无歌曲名兜底
            if mood == "energetic":
                return f"{theme}的节奏继续，准备好迎接下一段旅程了吗？"
            elif mood == "warm":
                return f"继续享受{theme}的温暖时光..."
            elif mood == "reflective":
                return f"让思绪在{theme}的旋律中飘一会儿..."
            else:
                return f"继续播放{theme}的音乐..."


# 模块级单例
dj_host_service = DJHostService()
