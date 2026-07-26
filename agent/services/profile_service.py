"""ProfileService — LLM 驱动的音乐画像服务。

从本地所有歌单收集歌曲样本，调用 LLM 分析生成 MusicProfile，
存储到 memory.json preference.music_profile。

关键设计：
  - MAX_PROFILE_SONGS = 500：去重 + 频率排序截断
  - _save_music_profile() 唯一写入口 + asyncio.Lock() 防并发
  - start()/stop() 空桩，与 ProviderAccountService 接口统一
"""

import asyncio
import logging
import time
from collections import Counter

from agent.state import playlist_store
from agent.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

MAX_PROFILE_SONGS = 500


class ProfileService:
    """音乐画像服务。

    收集本地歌单歌曲 → LLM 分析 → 存储画像。
    start()/stop() 空桩，与 ProviderAccountService 接口统一。
    """

    def __init__(self, llm_service=None, memory_service=None):
        self._llm = llm_service
        self._memory = memory_service or MemoryService()
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self):
        self._running = True
        logger.info("ProfileService started")

    async def stop(self):
        self._running = False
        logger.info("ProfileService stopped")

    async def analyze(self) -> dict:
        """分析本地歌单歌曲，生成/更新音乐画像。

        Returns:
            成功：{"ok": True, "profile": MusicProfile dict}
            失败：{"ok": False, "error": "..."}
        """
        async with self._lock:
            songs = self._collect_songs()
            if not songs:
                return {"ok": False, "error": "no songs in local playlists"}

            sampled = self._deduplicate_and_sample(songs)
            prompt = self._build_prompt(sampled)

            llm_result = await self._llm.call_json(prompt, temperature=0.5)
            if not llm_result.get("ok"):
                return {"ok": False, "error": llm_result.get("error", {}).get("message", "LLM call failed")}

            profile = llm_result["data"]
            profile["based_on_song_count"] = len(songs)
            profile["original_song_count"] = len(sampled)
            profile["sample_strategy"] = "frequency_top_500" if len(songs) > MAX_PROFILE_SONGS else "all"
            profile["last_analyzed_at"] = int(time.time() * 1000)

            self._save_music_profile(profile)
            return {"ok": True, "profile": profile}

    def _collect_songs(self) -> list[dict]:
        """从所有本地歌单收集歌曲。"""
        all_songs = []
        for pl in playlist_store.list_all():
            pid = pl.get("playlist_id", "")
            all_songs.extend(playlist_store.load_songs(pid))
        return all_songs

    def _deduplicate_and_sample(self, songs: list[dict]) -> list[dict]:
        """去重 + 频率排序 + 截断到 MAX_PROFILE_SONGS。

        - 有 id 的歌曲按 id 去重，按出现频率降序排列
        - 无 id 的歌曲直接追加
        """
        freq: Counter = Counter()
        for s in songs:
            sid = s.get("id", "") or s.get("song_id", "")
            if sid:
                freq[sid] += 1

        id_to_song: dict[str, dict] = {}
        for s in songs:
            sid = s.get("id", "") or s.get("song_id", "")
            if sid:
                id_to_song[sid] = s  # 后出现的覆盖，保留最新

        ordered = []
        for sid, _ in freq.most_common():
            if sid in id_to_song:
                ordered.append(id_to_song[sid])

        result = ordered[:MAX_PROFILE_SONGS]
        return result

    def _build_prompt(self, songs: list[dict]) -> str:
        """构建 LLM 分析 prompt。"""
        song_lines = []
        for s in songs:
            name = s.get("name", "未知")
            artists = s.get("artists") or []
            artist_str = ", ".join(
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in artists
            )
            song_lines.append(f"- {name} / {artist_str}")

        songs_text = "\n".join(song_lines)

        return (
            "You are a music analysis AI. Analyze the following list of songs and "
            "create a comprehensive music profile for the listener.\n\n"
            'Return a JSON object with these fields:\n'
            '- "energy_baseline": float 0.0-1.0\n'
            '- "tempo_preference": "fast" | "moderate" | "slow" | "mixed"\n'
            '- "mood_distribution": dict (e.g. {"happy": 0.3, "melancholic": 0.2})\n'
            '- "era_affinity": dict (e.g. {"2020s": 0.5, "2010s": 0.3})\n'
            '- "vocal_preference": "male_lead" | "female_lead" | "instrumental" | "mixed"\n'
            '- "discovery_openness": float 0.0-1.0\n'
            '- "listening_pattern": "focused" | "background" | "mixed"\n'
            '- "confidence": float 0.0-1.0\n'
            '- "favorite_genres": list[str]\n'
            '- "favorite_artists": list[str]\n'
            '- "music_preference_desc": str (a 2-3 sentence Chinese description)\n\n'
            f"Songs to analyze:\n{songs_text[:8000]}\n\n"
            "Return ONLY the JSON object, no markdown, no explanation."
        )

    def _save_music_profile(self, profile: dict):
        """保存音乐画像到 memory.json。

        asyncio.Lock() 在 analyze() 调用处保证串行写入。
        """
        self._memory.write("preference", "music_profile", profile)
        self._memory.write("profile", "favorite_genres", profile.get("favorite_genres", []))
        self._memory.write("profile", "favorite_artists", profile.get("favorite_artists", []))
        self._memory.write("profile", "music_preference_desc", profile.get("music_preference_desc", ""))
        self._memory.write(
            "profile", "AI_conclustion",
            f"基于 {profile.get('based_on_song_count', 0)} 首歌曲分析",
        )
        self._memory.write("profile", "update_at", profile.get("last_analyzed_at", 0))
        logger.info("Music profile saved (based on %d songs)", profile.get("based_on_song_count", 0))


# ── 模块级单例 ──

_profile_service: "ProfileService | None" = None


def set_profile_service(svc: ProfileService):
    global _profile_service
    _profile_service = svc


def get_profile_service() -> ProfileService | None:
    return _profile_service
