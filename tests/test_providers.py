"""v9.14 多数据源 Provider 测试。

覆盖：
  1. ProviderSearchResult 数据模型
  2. NeteaseProvider._to_result 格式转换
  3. QQProvider._to_result 格式转换
  4. SongResolver.resolve() — 合并 + 跨 provider 排重 + 评分
  5. MusicSearchService — 搜索分发（mock provider）
  6. ProviderRegistry 注册和健康检查
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.services.providers.base import MusicProvider, ProviderSearchResult, SongSource
from agent.services.providers.netease_provider import NeteaseProvider
from agent.services.providers.qq_provider import QQProvider
from agent.services.providers.registry import ProviderRegistry
from agent.services.song_resolver import resolve


# ═══════════════════════════════════════════════════════════════
# ProviderSearchResult
# ═══════════════════════════════════════════════════════════════


class TestProviderSearchResult:
    """ProviderSearchResult 数据模型基础测试。"""

    def test_basic_creation(self):
        result = ProviderSearchResult(
            provider="netease",
            platform_id="12345",
            name="夜曲",
            artists=[{"id": "1", "name": "周杰伦"}],
            album={"id": "1", "name": "叶惠美"},
            cover_url="http://cover.url",
            duration_ms=240000,
        )
        assert result.provider == "netease"
        assert result.platform_id == "12345"
        assert result.platform_mid is None
        assert result.name == "夜曲"
        assert result.artists[0]["name"] == "周杰伦"
        assert result.duration_ms == 240000

    def test_with_platform_mid(self):
        """QQ 音乐有 platform_mid。"""
        result = ProviderSearchResult(
            provider="qqmusic",
            platform_id="67890",
            platform_mid="abc123",
            name="夜曲",
        )
        assert result.platform_mid == "abc123"


# ═══════════════════════════════════════════════════════════════
# NeteaseProvider._to_result
# ═══════════════════════════════════════════════════════════════


class TestNeteaseProviderToResult:
    """NeteaseProvider._to_result 格式转换。"""

    def setup_method(self):
        self.provider = NeteaseProvider(base_url="http://localhost:8081/api/v1")

    def test_artists_format(self):
        """artists 字段的正确转换。"""
        raw = {
            "id": "12345",
            "name": "夜曲",
            "artists": [{"id": 1, "name": "周杰伦"}],
            "album": {"id": "1", "name": "叶惠美", "cover_url": "http://cover.url"},
            "duration_ms": 240000,
            "fee": 8,
        }
        result = self.provider._to_result(raw)
        assert result.provider == "netease"
        assert result.platform_id == "12345"
        assert result.name == "夜曲"
        assert result.artists[0]["id"] == "1"
        assert result.artists[0]["name"] == "周杰伦"
        assert result.album["name"] == "叶惠美"
        assert result.duration_ms == 240000
        assert result.cover_url == "http://cover.url"

    def test_ar_fallback(self):
        """兼容 ar 字段。"""
        raw = {
            "id": "54321",
            "name": "稻香",
            "ar": [{"id": 2, "name": "周杰伦"}],
            "al": {"id": "2", "name": "魔杰座"},
            "duration_ms": 180000,
        }
        result = self.provider._to_result(raw)
        assert result.provider == "netease"
        assert result.artists[0]["name"] == "周杰伦"
        assert result.album["name"] == "魔杰座"


# ═══════════════════════════════════════════════════════════════
# QQProvider._to_result
# ═══════════════════════════════════════════════════════════════


class TestQQProviderToResult:
    """QQProvider._to_result 格式转换。"""

    def setup_method(self):
        self.provider = QQProvider(base_url="http://localhost:8082")

    def test_basic_conversion(self):
        """标准 QQ Song 格式转 ProviderSearchResult。"""
        raw = {
            "id": 67890,
            "mid": "abc123",
            "name": "夜曲",
            "singer": [{"id": 1, "mid": "singer_mid", "name": "周杰伦"}],
            "album": {"id": 100, "mid": "album_mid", "name": "叶惠美"},
            "interval": 240,
            "pay": {"pay_play": 1},
        }
        result = self.provider._to_result(raw)
        assert result.provider == "qqmusic"
        assert result.platform_id == "67890"
        assert result.platform_mid == "abc123"
        assert result.name == "夜曲"
        assert result.artists[0]["name"] == "周杰伦"
        assert result.album["name"] == "叶惠美"
        assert result.duration_ms == 240000
        assert "album_mid" in result.cover_url  # QQ 封面 URL 包含 album_mid
        assert result.fee == 1

    def test_no_mid(self):
        """mid 为 None 的场景。"""
        raw = {
            "id": 67890,
            "name": "夜曲",
            "singer": [],
            "album": {},
            "interval": 0,
        }
        result = self.provider._to_result(raw)
        assert result.platform_mid is None
        assert result.duration_ms == 0


class TestQQProviderPlaylistToResult:
    """QQProvider._playlist_to_result 歌单 API 格式转换。"""

    def setup_method(self):
        self.provider = QQProvider(base_url="http://localhost:8082")

    def test_basic_conversion(self):
        """歌单 Song 格式转 ProviderSearchResult。"""
        raw = {
            "id": 12345,
            "mid": "song_mid_abc",
            "name": "夜曲",
            "singer": [{"id": 1, "mid": "singer_mid", "name": "周杰伦"}],
            "album": {"id": 100, "mid": "album_mid_xyz", "name": "叶惠美"},
            "interval": 240,
            "pay": {"pay_play": 1},
        }
        result = self.provider._playlist_to_result(raw)
        assert result.provider == "qqmusic"
        assert result.platform_id == "12345"
        assert result.platform_mid == "song_mid_abc"
        assert result.name == "夜曲"
        assert result.artists[0]["name"] == "周杰伦"
        assert result.album["name"] == "叶惠美"
        assert result.duration_ms == 240000
        assert "album_mid_xyz" in result.cover_url
        assert result.fee == 1

    def test_no_pay_dict(self):
        """pay 为空 dict 时 fee=0。"""
        raw = {"id": 1, "mid": "m1", "name": "歌", "singer": [], "album": {}, "interval": 100, "pay": {}}
        result = self.provider._playlist_to_result(raw)
        assert result.fee == 0

    def test_no_mid(self):
        """mid 为 None 时 platform_mid=None。"""
        raw = {"id": 1, "name": "歌", "singer": [], "album": {}, "interval": 100}
        result = self.provider._playlist_to_result(raw)
        assert result.platform_mid is None
        assert result.cover_url == ""


class TestGetPlaylistTracks:
    """Provider.get_playlist_tracks 方法（mock HTTP）。"""

    @pytest.mark.asyncio
    async def test_netease_success(self):
        """NeteaseProvider 成功获取歌单歌曲。"""
        import httpx

        def handler(request):
            return httpx.Response(200, json={
                "code": 0,
                "data": {
                    "songs": [
                        {"id": "1", "name": "夜曲", "artists": [{"id": 1, "name": "周杰伦"}],
                         "album": {"id": "1", "name": "叶惠美", "cover_url": "http://cover"}, "duration_ms": 240000, "fee": 0},
                        {"id": "2", "name": "晴天", "artists": [{"id": 1, "name": "周杰伦"}],
                         "album": {"id": "2", "name": "叶惠美"}, "duration_ms": 200000, "fee": 8},
                    ]
                }
            })

        provider = NeteaseProvider(base_url="http://test")
        await provider._client.aclose()
        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")

        results = await provider.get_playlist_tracks("123")
        assert len(results) == 2
        assert results[0].provider == "netease"
        assert results[0].platform_id == "1"
        assert results[0].name == "夜曲"
        assert results[1].platform_id == "2"

    @pytest.mark.asyncio
    async def test_netease_api_error(self):
        """Netease API 返回错误 → []。"""
        import httpx

        def handler(request):
            return httpx.Response(200, json={"code": -1, "msg": "not found"})

        provider = NeteaseProvider(base_url="http://test")
        await provider._client.aclose()
        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")

        results = await provider.get_playlist_tracks("999")
        assert results == []

    @pytest.mark.asyncio
    async def test_netease_http_error(self):
        """HTTP 请求异常 → []。"""
        import httpx

        def handler(request):
            raise httpx.RequestError("connection failed")

        provider = NeteaseProvider(base_url="http://test")
        await provider._client.aclose()
        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")

        results = await provider.get_playlist_tracks("123")
        assert results == []

    @pytest.mark.asyncio
    async def test_qq_success(self):
        """QQProvider 成功获取歌单歌曲。"""
        import httpx

        def handler(request):
            return httpx.Response(200, json={
                "code": 0,
                "songs": [
                    {"id": 123, "mid": "mid1", "name": "夜曲",
                     "singer": [{"id": 1, "name": "周杰伦"}],
                     "album": {"id": 100, "mid": "album_mid", "name": "叶惠美"},
                     "interval": 240, "pay": {"pay_play": 1}},
                    {"id": 456, "mid": "mid2", "name": "晴天",
                     "singer": [], "album": {}, "interval": 200, "pay": {}},
                ]
            })

        provider = QQProvider(base_url="http://test")
        await provider._client.aclose()
        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")

        results = await provider.get_playlist_tracks("789")
        assert len(results) == 2
        assert results[0].provider == "qqmusic"
        assert results[0].platform_id == "123"
        assert results[0].platform_mid == "mid1"
        assert results[0].duration_ms == 240000
        assert results[0].fee == 1
        assert results[1].platform_id == "456"
        assert results[1].fee == 0

    @pytest.mark.asyncio
    async def test_qq_api_error(self):
        """QQ API 返回错误 → []。"""
        import httpx

        def handler(request):
            return httpx.Response(200, json={"code": -1, "msg": "not found"})

        provider = QQProvider(base_url="http://test")
        await provider._client.aclose()
        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")

        results = await provider.get_playlist_tracks("999")
        assert results == []

    @pytest.mark.asyncio
    async def test_default_implementation(self):
        """默认实现返回 []。"""
        from agent.services.providers.base import MusicProvider

        class _MinimalProvider(MusicProvider):
            @property
            def name(self) -> str:
                return "test"
            async def search(self, query, limit=10): return []
            async def get_play_url(self, source): return None
            async def health_check(self): return False

        provider = _MinimalProvider()
        results = await provider.get_playlist_tracks("any")
        assert results == []


# ═══════════════════════════════════════════════════════════════
# SongResolver.resolve()
# ═══════════════════════════════════════════════════════════════


class TestResolve:
    """SongResolver.resolve() 多 Provider 融合。"""

    def test_single_provider(self):
        """单 Provider 返回正常。"""
        results = {
            "netease": [
                ProviderSearchResult(provider="netease", platform_id="1", name="晴天",
                                     artists=[{"name": "周杰伦"}], album={}),
            ]
        }
        songs = resolve(results)
        assert len(songs) == 1
        assert songs[0]["id"] == "1"
        assert songs[0]["provider"] == "netease"

    def test_cross_provider_merge(self):
        """同一首歌来自两个 Provider → 合并为一条，sources 含两个 entry。"""
        results = {
            "netease": [
                ProviderSearchResult(provider="netease", platform_id="1", name="夜曲",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
            "qqmusic": [
                ProviderSearchResult(provider="qqmusic", platform_id="2", platform_mid="mid2",
                                     name="夜曲", artists=[{"name": "周杰伦"}], album={}),
            ],
        }
        songs = resolve(results)
        assert len(songs) == 1, "同一首歌应合并为一条"
        song = songs[0]
        assert len(song["sources"]) == 2
        providers = {s["provider"] for s in song["sources"]}
        assert providers == {"netease", "qqmusic"}

    def test_cross_provider_alias_merge(self):
        """英文名 + 中文名跨 Provider 合并。"""
        results = {
            "netease": [
                ProviderSearchResult(provider="netease", platform_id="1", name="夜曲",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
            "qqmusic": [
                ProviderSearchResult(provider="qqmusic", platform_id="2", name="夜曲",
                                     artists=[{"name": "Jay Chou"}], album={}),
            ],
        }
        songs = resolve(results)
        assert len(songs) == 1, "别名应合并"
        assert len(songs[0]["sources"]) == 2

    def test_provider_default_id(self):
        """默认 Provider（netease）的 platform_id 作为 Song.id。"""
        results = {
            "netease": [
                ProviderSearchResult(provider="netease", platform_id="netease_1", name="晴天",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
            "qqmusic": [
                ProviderSearchResult(provider="qqmusic", platform_id="qq_1", name="晴天",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
        }
        songs = resolve(results, default_provider="netease")
        assert songs[0]["id"] == "netease_1"

    def test_no_overlap(self):
        """不同歌曲不合并。"""
        results = {
            "netease": [
                ProviderSearchResult(provider="netease", platform_id="1", name="晴天",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
            "qqmusic": [
                ProviderSearchResult(provider="qqmusic", platform_id="2", name="江南",
                                     artists=[{"name": "林俊杰"}], album={}),
            ],
        }
        songs = resolve(results)
        assert len(songs) == 2

    def test_empty_results(self):
        """空 Provider 结果 → 空列表。"""
        assert resolve({}) == []
        assert resolve({"netease": []}) == []
        assert resolve({"netease": [], "qqmusic": []}) == []

    def test_original_over_live_in_merge(self):
        """merge 时原版优先于 Live 版作为 displayed song。"""
        results = {
            "netease": [
                ProviderSearchResult(provider="netease", platform_id="live1", name="晴天(Live)",
                                     artists=[{"name": "周杰伦"}], album={}),
                ProviderSearchResult(provider="netease", platform_id="orig1", name="晴天",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
        }
        songs = resolve(results)
        assert len(songs) == 1
        # 原版优先 → id 应为 orig1
        assert songs[0]["id"] == "orig1"

    def test_sources_play_available(self):
        """所有 source 标记 play_available=True。"""
        results = {
            "netease": [
                ProviderSearchResult(provider="netease", platform_id="1", name="晴天",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
            "qqmusic": [
                ProviderSearchResult(provider="qqmusic", platform_id="2", name="晴天",
                                     artists=[{"name": "周杰伦"}], album={}),
            ],
        }
        songs = resolve(results)
        for src in songs[0]["sources"]:
            assert src["play_available"] is True


# ═══════════════════════════════════════════════════════════════
# ProviderRegistry
# ═══════════════════════════════════════════════════════════════


class TestProviderRegistry:
    """ProviderRegistry 注册和查询。"""

    def test_register_and_get(self):
        registry = ProviderRegistry()
        provider = NeteaseProvider(base_url="http://localhost:8081/api/v1")
        registry.register(provider)
        assert registry.get("netease") is provider
        assert registry.get("qqmusic") is None

    def test_list_names(self):
        registry = ProviderRegistry()
        registry.register(NeteaseProvider(base_url="http://localhost:8081/api/v1"))
        registry.register(QQProvider(base_url="http://localhost:8082"))
        names = registry.list_names()
        assert "netease" in names
        assert "qqmusic" in names

    def test_get_all(self):
        registry = ProviderRegistry()
        p1 = NeteaseProvider(base_url="http://localhost:8081/api/v1")
        p2 = QQProvider(base_url="http://localhost:8082")
        registry.register(p1)
        registry.register(p2)
        all_providers = registry.get_all()
        assert len(all_providers) == 2

    def test_health_check_all_timeout(self):
        """对不存在的服务做健康检查 → 全部返回 False，不崩溃。"""
        registry = ProviderRegistry()
        registry.register(NeteaseProvider(base_url="http://localhost:19999"))
        registry.register(QQProvider(base_url="http://localhost:19998"))
        import asyncio
        results = asyncio.run(registry.health_check_all(timeout=0.5))
        assert all(ok is False for ok in results.values())


# ═══════════════════════════════════════════════════════════════
# MusicSearchService（mock provider）
# ═══════════════════════════════════════════════════════════════


class _MockProvider(MusicProvider):
    """模拟 Provider 供单元测试。"""

    def __init__(self, name: str, results: list[ProviderSearchResult], fail: bool = False):
        self._name = name
        self._results = results
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    async def search(self, query: str, limit: int = 10) -> list[ProviderSearchResult]:
        if self._fail:
            raise RuntimeError("mock search failure")
        return self._results[:limit]

    async def get_play_url(self, source) -> str | None:
        return None

    async def health_check(self) -> bool:
        return not self._fail


class TestMusicSearchService:
    """MusicSearchService 搜索分发和故障隔离。"""

    @pytest.mark.asyncio
    async def test_search_normal(self):
        from agent.services.search_service import MusicSearchService

        registry = ProviderRegistry()
        registry.register(_MockProvider("netease", [
            ProviderSearchResult(provider="netease", platform_id="1", name="晴天", artists=[{"name": "周杰伦"}], album={}),
        ]))
        registry.register(_MockProvider("qqmusic", [
            ProviderSearchResult(provider="qqmusic", platform_id="2", name="晴天", artists=[{"name": "周杰伦"}], album={}),
        ]))

        svc = MusicSearchService(registry)
        results = await svc.search("晴天")
        assert "netease" in results
        assert "qqmusic" in results
        assert len(results["netease"]) == 1
        assert len(results["qqmusic"]) == 1

    @pytest.mark.asyncio
    async def test_one_provider_fails(self):
        """一个 Provider 挂了不影响另一个。"""
        from agent.services.search_service import MusicSearchService

        registry = ProviderRegistry()
        registry.register(_MockProvider("netease", [
            ProviderSearchResult(provider="netease", platform_id="1", name="晴天", artists=[{"name": "周杰伦"}], album={}),
        ], fail=True))
        registry.register(_MockProvider("qqmusic", [
            ProviderSearchResult(provider="qqmusic", platform_id="2", name="晴天", artists=[{"name": "周杰伦"}], album={}),
        ]))

        svc = MusicSearchService(registry)
        results = await svc.search("晴天")
        assert "netease" not in results, "失败的 Provider 不应出现在结果中"
        assert "qqmusic" in results

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        """所有 Provider 都挂 → 空结果，不崩溃。"""
        from agent.services.search_service import MusicSearchService

        registry = ProviderRegistry()
        registry.register(_MockProvider("netease", [], fail=True))
        registry.register(_MockProvider("qqmusic", [], fail=True))

        svc = MusicSearchService(registry)
        results = await svc.search("晴天")
        assert results == {}

    @pytest.mark.asyncio
    async def test_no_providers(self):
        """空 registry → 空结果。"""
        from agent.services.search_service import MusicSearchService

        registry = ProviderRegistry()
        svc = MusicSearchService(registry)
        results = await svc.search("晴天")
        assert results == {}

    @pytest.mark.asyncio
    async def test_filtered_provider_names(self):
        """指定 provider_names 参数筛选。"""
        from agent.services.search_service import MusicSearchService

        registry = ProviderRegistry()
        registry.register(_MockProvider("netease", [
            ProviderSearchResult(provider="netease", platform_id="1", name="晴天", artists=[{"name": "周杰伦"}], album={}),
        ]))
        registry.register(_MockProvider("qqmusic", [
            ProviderSearchResult(provider="qqmusic", platform_id="2", name="晴天", artists=[{"name": "周杰伦"}], album={}),
        ]))

        svc = MusicSearchService(registry)
        results = await svc.search("晴天", provider_names=["netease"])
        assert "netease" in results
        assert "qqmusic" not in results


# ═══════════════════════════════════════════════════════════════
# P2: SongSource + SourceSelector + executor
# ═══════════════════════════════════════════════════════════════


class TestSongSource:
    """SongSource 数据模型。"""

    def test_basic_creation(self):
        source = SongSource(provider="netease", platform_id="12345")
        assert source.provider == "netease"
        assert source.platform_id == "12345"
        assert source.platform_mid is None
        assert source.play_available is True

    def test_with_platform_mid(self):
        source = SongSource(provider="qqmusic", platform_id="67890", platform_mid="mid123")
        assert source.platform_mid == "mid123"

    def test_play_available_false(self):
        source = SongSource(provider="netease", platform_id="1", play_available=False)
        assert source.play_available is False

    def test_from_dict_minimal(self):
        d = {"provider": "netease", "platform_id": "1"}
        source = SongSource.from_dict(d)
        assert source.provider == "netease"
        assert source.platform_id == "1"
        assert source.platform_mid is None
        assert source.play_available is True

    def test_from_dict_full(self):
        d = {"provider": "qqmusic", "platform_id": "2", "platform_mid": "mid2", "play_available": False}
        source = SongSource.from_dict(d)
        assert source.provider == "qqmusic"
        assert source.platform_mid == "mid2"
        assert source.play_available is False

    def test_from_dict_missing_provider_key(self):
        """缺少 provider 应抛 KeyError（调用方保证 sources 格式正确）。"""
        import pytest as _pt
        with _pt.raises(KeyError):
            SongSource.from_dict({"platform_id": "1"})

    def test_from_dict_missing_platform_id(self):
        """缺少 platform_id 应抛 KeyError。"""
        import pytest as _pt
        with _pt.raises(KeyError):
            SongSource.from_dict({"provider": "netease"})


class TestSourceSelector:
    """SourceSelector.rank() 排序和过滤。"""

    def test_rank_netease_priority(self):
        """netease 排在 qqmusic 前面（默认优先级）。"""
        from agent.services.source_selector import SourceSelector

        selector = SourceSelector(ProviderRegistry())
        song = {
            "sources": [
                {"provider": "qqmusic", "platform_id": "2"},
                {"provider": "netease", "platform_id": "1"},
            ]
        }
        ranked = selector.rank(song)
        assert len(ranked) == 2
        assert ranked[0].provider == "netease"
        assert ranked[1].provider == "qqmusic"

    def test_rank_custom_priority(self):
        """自定义优先级：qqmusic 优先。"""
        from agent.services.source_selector import SourceSelector

        selector = SourceSelector(ProviderRegistry(), provider_priority=["qqmusic", "netease"])
        song = {
            "sources": [
                {"provider": "netease", "platform_id": "1"},
                {"provider": "qqmusic", "platform_id": "2"},
            ]
        }
        ranked = selector.rank(song)
        assert ranked[0].provider == "qqmusic"
        assert ranked[1].provider == "netease"

    def test_rank_filters_play_available_false(self):
        """play_available=False 的 source 被过滤。"""
        from agent.services.source_selector import SourceSelector

        selector = SourceSelector(ProviderRegistry())
        song = {
            "sources": [
                {"provider": "netease", "platform_id": "1", "play_available": False},
                {"provider": "qqmusic", "platform_id": "2", "play_available": True},
            ]
        }
        ranked = selector.rank(song)
        assert len(ranked) == 1
        assert ranked[0].provider == "qqmusic"

    def test_rank_all_unavailable(self):
        """全部不可用 → 空列表。"""
        from agent.services.source_selector import SourceSelector

        selector = SourceSelector(ProviderRegistry())
        song = {
            "sources": [
                {"provider": "netease", "platform_id": "1", "play_available": False},
            ]
        }
        assert selector.rank(song) == []

    def test_rank_empty_sources(self):
        """空 sources[] → 空列表。"""
        from agent.services.source_selector import SourceSelector

        selector = SourceSelector(ProviderRegistry())
        assert selector.rank({"sources": []}) == []
        assert selector.rank({}) == []

    def test_rank_unknown_provider_sorted_last(self):
        """不在优先级列表中的 provider 排最后。"""
        from agent.services.source_selector import SourceSelector

        selector = SourceSelector(ProviderRegistry(), provider_priority=["netease"])
        song = {
            "sources": [
                {"provider": "unknown", "platform_id": "x"},
                {"provider": "netease", "platform_id": "1"},
            ]
        }
        ranked = selector.rank(song)
        assert len(ranked) == 2
        assert ranked[0].provider == "netease"
        assert ranked[1].provider == "unknown"


class TestBuildSongPayload:
    """_build_song_payload sources 透传。"""

    def test_passthrough_sources(self):
        """sources 字段透传到输出。"""
        from agent.nodes.action_planner import _build_song_payload

        raw = {
            "song_id": "123",
            "name": "夜曲",
            "artists": [{"id": "1", "name": "周杰伦"}],
            "album": {"id": "1", "name": "叶惠美"},
            "cover_url": "http://cover",
            "duration_ms": 240000,
            "fee": 0,
            "sources": [
                {"provider": "netease", "platform_id": "123"},
                {"provider": "qqmusic", "platform_id": "456", "platform_mid": "mid456"},
            ],
        }
        result = _build_song_payload(raw)
        assert "sources" in result
        assert len(result["sources"]) == 2
        assert result["sources"][0]["provider"] == "netease"
        assert result["sources"][1]["platform_mid"] == "mid456"

    def test_no_sources_default_empty(self):
        """无 sources 字段 → 默认 []。"""
        from agent.nodes.action_planner import _build_song_payload

        raw = {"song_id": "123", "name": "夜曲", "artists": [], "album": {}}
        result = _build_song_payload(raw)
        assert "sources" in result
        assert result["sources"] == []


class TestExecPlaySources:
    """ActionExecutor._exec_play 通过 PlayService 解析（P5 统一入口）。"""

    @pytest.mark.asyncio
    async def test_play_service_success(self):
        """play_service.play 返回 URL → _exec_play 写回 payload。"""
        from unittest.mock import patch, AsyncMock
        from agent.nodes.action_executor import _exec_play

        params = {"song_id": "12345"}
        payload = {"music_play": {"song": {"name": "夜曲", "artists": []}}}

        with patch("agent.services.play_service.play_service.play",
                   new_callable=AsyncMock) as mock_play:
            mock_play.return_value = {
                "play_url": "http://proxy.url/audio?url=xxx&provider=netease",
                "song": {"name": "夜曲", "artists": []},
                "provider_name": "netease",
            }
            result = await _exec_play(payload, params)

        assert result is None, "成功时返回 None"
        mock_play.assert_awaited_once()
        # play_url 写回 payload
        assert "play_url" in payload.get("music_play", {})

    @pytest.mark.asyncio
    async def test_play_service_returns_none(self):
        """play_service.play 返回 None → PLAY_URL_NOT_FOUND。"""
        from unittest.mock import patch, AsyncMock
        from agent.nodes.action_executor import _exec_play

        params = {"song_id": "12345"}
        payload = {"music_play": {"song": {"name": "夜曲"}}}

        with patch("agent.services.play_service.play_service.play",
                   new_callable=AsyncMock, return_value=None):
            result = await _exec_play(payload, params)

        assert result is not None
        assert result["code"] == "PLAY_URL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_play_service_raises(self):
        """play_service.play 抛异常 → PLAY_FAILED。"""
        from unittest.mock import patch, AsyncMock
        from agent.nodes.action_executor import _exec_play

        params = {"song_id": "12345"}
        payload = {"music_play": {"song": {}}}

        with patch("agent.services.play_service.play_service.play",
                   new_callable=AsyncMock,
                   side_effect=ConnectionError("API timeout")):
            result = await _exec_play(payload, params)

        assert result is not None
        assert result["code"] == "PLAY_FAILED"

    @pytest.mark.asyncio
    async def test_empty_song_id_skips(self):
        """空 song_id → 安全跳过。"""
        from agent.nodes.action_executor import _exec_play

        result = await _exec_play({}, {"song_id": ""})
        assert result is None
