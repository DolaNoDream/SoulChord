"""recommend_music 工具 + _match_pre_resolved_song 单元测试。

覆盖：
1. _match_pre_resolved_song 基本匹配（歌名归一化）
2. _match_pre_resolved_song 歌手相似度匹配
3. _match_pre_resolved_song 不匹配
4. _match_pre_resolved_song 空 name
5. adapter._recommend_music 解析路径

使用方法：
    cd dev
    python -m pytest tests/test_recommend_music.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ═══════════════════════════════════════════════════════════════
# Test Case 1: _match_pre_resolved_song
# ═══════════════════════════════════════════════════════════════
class TestMatchPreResolvedSong:
    """从 recommend_music 结果匹配已解析歌曲。"""

    def test_match_by_name(self):
        """歌名匹配 → 返回已解析歌曲 + song_id。"""
        from agent.nodes.action_planner import _match_pre_resolved_song

        tool_msgs = [
            {
                "name": "recommend_music",
                "result": {
                    "songs": [
                        {"id": "108914", "name": "江南", "artist": "林俊杰",
                         "artists": [{"id": "", "name": "林俊杰"}]},
                        {"id": "25642214", "name": "爱错(Live)", "artist": "王力宏",
                         "artists": [{"id": "", "name": "王力宏"}]},
                    ],
                },
            },
        ]

        song, song_id = _match_pre_resolved_song("江南", "林俊杰", tool_msgs)
        assert song_id == "108914"
        assert song["name"] == "江南"

    def test_match_normalized_name(self):
        """归一化歌名也能匹配。"""
        from agent.nodes.action_planner import _match_pre_resolved_song

        tool_msgs = [
            {
                "name": "recommend_music",
                "result": {
                    "songs": [
                        {"id": "999", "name": "告白气球", "artist": "周杰伦",
                         "artists": [{"id": "", "name": "周杰伦"}]},
                    ],
                },
            },
        ]

        # 带 artist 后缀的歌名
        song, song_id = _match_pre_resolved_song("告白气球", "周杰伦", tool_msgs)
        assert song_id == "999"

    def test_match_by_artist_similarity(self):
        """歌手相似度 ≥ 0.3 时匹配。"""
        from agent.nodes.action_planner import _match_pre_resolved_song

        tool_msgs = [
            {
                "name": "recommend_music",
                "result": {
                    "songs": [
                        {"id": "108914", "name": "江南", "artist": "林俊杰",
                         "artists": [{"id": "", "name": "林俊杰"}]},
                    ],
                },
            },
        ]

        # 歌手名不完全匹配但有足够相似度
        song, song_id = _match_pre_resolved_song("江南", "JJ林俊杰", tool_msgs)
        assert song_id == "108914"

    def test_no_match_different_name(self):
        """歌名不同 → 返回 None, ''。"""
        from agent.nodes.action_planner import _match_pre_resolved_song

        tool_msgs = [
            {
                "name": "recommend_music",
                "result": {
                    "songs": [
                        {"id": "108914", "name": "江南", "artist": "林俊杰",
                         "artists": [{"id": "", "name": "林俊杰"}]},
                    ],
                },
            },
        ]

        song, song_id = _match_pre_resolved_song("七里香", "周杰伦", tool_msgs)
        assert song_id == ""
        assert song is None

    def test_empty_name(self):
        """空 name → 直接返回 None, ''。"""
        from agent.nodes.action_planner import _match_pre_resolved_song

        tool_msgs = [
            {
                "name": "recommend_music",
                "result": {
                    "songs": [
                        {"id": "108914", "name": "江南", "artist": "林俊杰"},
                    ],
                },
            },
        ]

        song, song_id = _match_pre_resolved_song("", "林俊杰", tool_msgs)
        assert song_id == ""
        assert song is None

    def test_multiple_messages_latest_first(self):
        """多条 recommend_music 消息时从最新开始匹配。"""
        from agent.nodes.action_planner import _match_pre_resolved_song

        tool_msgs = [
            {
                "name": "recommend_music",
                "result": {
                    "songs": [
                        {"id": "old1", "name": "江南", "artist": "林俊杰",
                         "artists": [{"id": "", "name": "林俊杰"}]},
                    ],
                },
            },
            {
                "name": "recommend_music",
                "result": {
                    "songs": [
                        {"id": "new1", "name": "江南", "artist": "林俊杰",
                         "artists": [{"id": "", "name": "林俊杰"}]},
                    ],
                },
            },
        ]

        # 应匹配最新的（第一条）= reversed 后的第一条
        song, song_id = _match_pre_resolved_song("江南", "林俊杰", tool_msgs)
        assert song_id == "new1"


# ═══════════════════════════════════════════════════════════════
# Test Case 2: _recommend_music
# ═══════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_recommend_music_resolves_songs():
    """_recommend_music 对每首歌曲搜索+解析。"""
    from agent.services.adapter import ToolAdapter
    from unittest.mock import patch, AsyncMock

    adapter = ToolAdapter()

    fake_results = [
        [{"id": "108914", "name": "江南", "artist": "林俊杰",
          "artists": [{"id": "", "name": "林俊杰"}], "sources": []}],
        [{"id": "25642214", "name": "爱错(Live)", "artist": "王力宏",
          "artists": [{"id": "", "name": "王力宏"}], "sources": []}],
    ]

    with patch.object(adapter, "_search_play_music", new=AsyncMock(side_effect=fake_results)):
        songs_input = [
            {"name": "江南", "artist": "林俊杰", "reason": "经典"},
            {"name": "爱错(Live)", "artist": "王力宏", "reason": "好听"},
        ]
        resolved = await adapter._recommend_music(songs_input)

        assert len(resolved) == 2
        assert resolved[0]["id"] == "108914"
        assert resolved[0]["_recommend_reason"] == "经典"
        assert resolved[1]["id"] == "25642214"
        assert resolved[1]["_recommend_reason"] == "好听"


@pytest.mark.asyncio
async def test_recommend_music_skips_empty_search():
    """搜索无结果时跳过（含空 name/artist 跳过）。"""
    from agent.services.adapter import ToolAdapter
    from unittest.mock import AsyncMock, patch

    adapter = ToolAdapter()

    with patch.object(adapter, "_search_play_music", new=AsyncMock(return_value=[])):
        songs_input = [
            {"name": "", "artist": "", "reason": "空"},
            {"name": "江南", "artist": "林俊杰", "reason": "经典"},
        ]
        resolved = await adapter._recommend_music(songs_input)

        assert len(resolved) == 0


@pytest.mark.asyncio
async def test_recommend_music_no_resolution():
    """搜索无结果时静默跳过。"""
    from agent.services.adapter import ToolAdapter
    from unittest.mock import AsyncMock, patch

    adapter = ToolAdapter()

    with patch.object(adapter, "_search_play_music", new=AsyncMock(return_value=[])):
        songs_input = [
            {"name": "不存在的歌", "artist": "不存在", "reason": "测试"},
        ]
        resolved = await adapter._recommend_music(songs_input)

        assert len(resolved) == 0
