"""Song Resolver 单元测试。

覆盖：
  1. normalize_song_name — 版本后缀去除
  2. pick_best_song — 原版优先于 Live/伴奏/翻唱
  3. dedup_candidates — 现有队列去重 + 同版本去重
  4. 跨 REPLAN 不重复
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.services.song_resolver import (
    normalize_song_name,
    pick_best_song,
    dedup_candidates,
)


# ═══════════════════════════════════════════════════════════════
# normalize_song_name
# ═══════════════════════════════════════════════════════════════


class TestNormalizeSongName:
    """normalize_song_name 正确去除版本后缀。"""

    def test_plain_name_unchanged(self):
        """无版本后缀的歌名 → 不变。"""
        assert normalize_song_name("晴天") == "晴天"
        assert normalize_song_name("江南") == "江南"
        assert normalize_song_name("Here Comes The Sun") == "here comes the sun"

    def test_live_suffix_removed(self):
        """(Live) 后缀 → 去除。"""
        assert normalize_song_name("晴天(Live)") == "晴天"
        assert normalize_song_name("晴天（Live）") == "晴天"
        assert normalize_song_name("爱错(Live)") == "爱错"

    def test_chinese_version_suffixes(self):
        """中文版本后缀 → 去除。"""
        assert normalize_song_name("晴天(伴奏)") == "晴天"
        assert normalize_song_name("晴天（伴奏）") == "晴天"
        assert normalize_song_name("晴天(翻唱)") == "晴天"
        assert normalize_song_name("晴天(钢琴版)") == "晴天"

    def test_dash_version_suffix(self):
        """'-' 分隔的版本后缀 → 去除。"""
        assert normalize_song_name("晴天 - Live") == "晴天"
        assert normalize_song_name("晴天-Live") == "晴天"
        assert normalize_song_name("晴天 - 伴奏") == "晴天"

    def test_english_version_suffixes(self):
        """英文版本后缀 → 去除。"""
        assert normalize_song_name("Happy (Remix)") == "happy"
        assert normalize_song_name("Happy - Instrumental").startswith("happy")
        assert normalize_song_name("Song (Cover)") == "song"


# ═══════════════════════════════════════════════════════════════
# pick_best_song
# ═══════════════════════════════════════════════════════════════


class TestPickBestSong:
    """pick_best_song 从搜索结果中选出最佳版本。"""

    def test_original_over_live(self):
        """原版优先于 Live 版本。"""
        name, artist = "晴天", "周杰伦"
        results = [
            {"id": "live1", "name": "晴天(Live)", "artists": [{"name": "周杰伦"}]},
            {"id": "orig1", "name": "晴天", "artists": [{"name": "周杰伦"}]},
        ]
        best = pick_best_song(name, artist, results)
        assert best is not None
        assert best["id"] == "orig1", "应选择原版而非 Live"

    def test_original_over_accompaniment(self):
        """原版优先于伴奏版。"""
        name, artist = "晴天", "周杰伦"
        results = [
            {"id": "acc1", "name": "晴天(伴奏)", "artists": [{"name": "周杰伦"}]},
            {"id": "orig1", "name": "晴天", "artists": [{"name": "周杰伦"}]},
        ]
        best = pick_best_song(name, artist, results)
        assert best is not None
        assert best["id"] == "orig1", "应选择原版而非伴奏"

    def test_artist_matching(self):
        """同名不同歌手 → 选出正确的歌手版本。"""
        name, artist = "晴天", "周杰伦"
        results = [
            {"id": "cover1", "name": "晴天", "artists": [{"name": "王俊凯"}]},
            {"id": "orig1", "name": "晴天", "artists": [{"name": "周杰伦"}]},
        ]
        best = pick_best_song(name, artist, results)
        assert best is not None
        assert best["id"] == "orig1", "应选择周杰伦版本"

    def test_no_match_returns_none(self):
        """无歌名匹配时返回 None，由调用者处理兜底。"""
        name, artist = "不存在的歌", "不存在"
        results = [
            {"id": "999", "name": "江南", "artists": [{"name": "林俊杰"}]},
        ]
        best = pick_best_song(name, artist, results)
        assert best is None

    def test_empty_results_returns_none(self):
        """空搜索结果 → 返回 None。"""
        best = pick_best_song("test", "test", [])
        assert best is None

    def test_many_versions_only_original(self):
        """10 个候选版本中只选出原版。"""
        name, artist = "晴天", "周杰伦"
        results = [
            {"id": "v1", "name": "晴天(Live)", "artists": [{"name": "周杰伦"}]},
            {"id": "v2", "name": "晴天(伴奏)", "artists": [{"name": "周杰伦"}]},
            {"id": "v3", "name": "晴天", "artists": [{"name": "周杰伦"}]},
            {"id": "v4", "name": "晴天(钢琴版)", "artists": [{"name": "周杰伦"}]},
            {"id": "v5", "name": "晴天 - Live", "artists": [{"name": "周杰伦"}]},
            {"id": "v6", "name": "晴天(翻唱)", "artists": [{"name": "周杰伦"}]},
            {"id": "v7", "name": "晴天(Remix)", "artists": [{"name": "周杰伦"}]},
            {"id": "v8", "name": "晴天(演唱会)", "artists": [{"name": "周杰伦"}]},
            {"id": "v9", "name": "晴天(演奏版)", "artists": [{"name": "周杰伦"}]},
            {"id": "v10", "name": "晴天 - Instrumental", "artists": [{"name": "周杰伦"}]},
        ]
        best = pick_best_song(name, artist, results)
        assert best is not None
        assert best["id"] == "v3", "应选择原版晴天(ID=v3)"


# ═══════════════════════════════════════════════════════════════
# dedup_candidates
# ═══════════════════════════════════════════════════════════════


class TestDedupCandidates:
    """dedup_candidates 正确去重。"""

    def test_dedup_same_song_id(self):
        """相同 song_id → 去重。"""
        candidates = [
            {"id": "1001", "name": "晴天", "artists": [{"name": "周杰伦"}]},
            {"id": "1001", "name": "晴天", "artists": [{"name": "周杰伦"}]},
        ]
        result = dedup_candidates(candidates)
        assert len(result) == 1

    def test_dedup_same_normalized_name(self):
        """相同归一化歌名（不同版本）→ 去重。"""
        candidates = [
            {"id": "1001", "name": "晴天", "artists": [{"name": "周杰伦"}]},
            {"id": "1002", "name": "晴天(Live)", "artists": [{"name": "周杰伦"}]},
            {"id": "1003", "name": "晴天(伴奏)", "artists": [{"name": "周杰伦"}]},
        ]
        result = dedup_candidates(candidates)
        # 只保留第一首（原版晴天）
        assert len(result) == 1
        assert result[0]["id"] == "1001"

    def test_against_existing_queue(self):
        """候选歌曲已在现有队列中 → 去重。"""
        candidates = [
            {"id": "2001", "name": "稻香", "artists": [{"name": "周杰伦"}]},
            {"id": "2002", "name": "七里香", "artists": [{"name": "周杰伦"}]},
        ]
        existing_queue = [
            {"song_id": "2001", "name": "稻香", "artist": "周杰伦", "source": "search"},
        ]
        result = dedup_candidates(candidates, existing_queue)
        assert len(result) == 1
        assert result[0]["id"] == "2002"

    def test_against_existing_normalized_name(self):
        """候选歌曲的归一化名已在现有队列中 → 去重。"""
        candidates = [
            {"id": "3002", "name": "晴天(Live)", "artists": [{"name": "周杰伦"}]},
        ]
        existing_queue = [
            {"song_id": "3001", "name": "晴天", "artist": "周杰伦", "source": "search"},
        ]
        result = dedup_candidates(candidates, existing_queue)
        assert len(result) == 0, "晴天(Live) 应被 '晴天' 去重"

    def test_current_song_id_excluded(self):
        """当前正在播放的 song_id → 排除。"""
        candidates = [
            {"id": "4001", "name": "晴天", "artists": [{"name": "周杰伦"}]},
            {"id": "4002", "name": "稻香", "artists": [{"name": "周杰伦"}]},
        ]
        result = dedup_candidates(candidates, current_song_id="4001")
        assert len(result) == 1
        assert result[0]["id"] == "4002"

    def test_empty_candidates(self):
        """空候选 → 返回空。"""
        assert dedup_candidates([]) == []

    def test_cross_replan_no_accumulation(self):
        """跨 REPLAN 测试：B 搜索结果不包含 A 的旧歌曲。"""
        # 模拟现有队列（REPLAN 1 剩余）
        existing = [
            {"song_id": "5001", "name": "稻香", "artist": "周杰伦", "source": "search"},
            {"song_id": "5002", "name": "七里香", "artist": "周杰伦", "source": "search"},
        ]
        # REPLAN 2 搜索结果（包含历史 + 新歌）
        candidates = [
            {"id": "5001", "name": "稻香", "artists": [{"name": "周杰伦"}]},  # 已在队列
            {"id": "5002", "name": "七里香", "artists": [{"name": "周杰伦"}]},  # 已在队列
            {"id": "6001", "name": "告白气球", "artists": [{"name": "周杰伦"}]},  # 新歌
            {"id": "6002", "name": "青花瓷", "artists": [{"name": "周杰伦"}]},  # 新歌
        ]
        result = dedup_candidates(candidates, existing)
        # 不应包含稻香和七里香（已在队列），只保留新歌
        assert len(result) == 2
        ids = {s["id"] for s in result}
        assert "6001" in ids
        assert "6002" in ids
        assert "5001" not in ids
        assert "5002" not in ids

    def test_dedup_same_name_different_artist(self):
        """同一歌曲不同歌手翻唱 → 去重（归一化歌名唯一 key）。"""
        candidates = [
            {"id": "7001", "name": "爱错(Live)", "artists": [{"name": "王力宏"}]},
            {"id": "7002", "name": "爱错", "artists": [{"name": "北夜"}]},
            {"id": "7003", "name": "爱错", "artists": [{"name": "王力宏的小迷妹"}]},
            {"id": "7004", "name": "江南", "artists": [{"name": "林俊杰"}]},
            {"id": "7005", "name": "江南（正式版）", "artists": [{"name": "林俊杰, 街道办"}]},
            {"id": "7006", "name": "江南", "artists": [{"name": "林俊杰-, 夏蔓蔓"}]},
        ]
        result = dedup_candidates(candidates)
        assert len(result) == 2  # 爱错 × 1 + 江南 × 1 = 2
        names = {normalize_song_name(s.get("name", "")) for s in result}
        assert "爱错" in names
        assert "江南" in names
