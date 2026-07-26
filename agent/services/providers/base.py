"""MusicProvider 抽象基类 + ProviderSearchResult 数据模型。

v9.14: 对称 Provider 抽象，NeteaseProvider 和 QQProvider 共享同一接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SongSource:
    """播放源选择结果：provider + 平台 ID。

    由 SourceSelector.rank() 生成，被 ActionExecutor 消费。
    配合 from_dict() 从 Song.sources[] 中的 dict 构造。
    """
    provider: str
    platform_id: str
    platform_mid: str | None = None
    play_available: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "SongSource":
        """从 sources[] 中的 dict 构造 SongSource。"""
        return cls(
            provider=data["provider"],
            platform_id=data["platform_id"],
            platform_mid=data.get("platform_mid"),
            play_available=data.get("play_available", True),
        )


@dataclass
class ProviderSearchResult:
    """Provider 搜索结果的标准化内部模型（不对外暴露）。

    各 Provider 将自有格式归一化为此类，由 SongResolver.resolve() 消费。
    """
    provider: str
    platform_id: str
    platform_mid: Optional[str] = None
    name: str = ""
    artists: list[dict] = field(default_factory=list)
    album: dict = field(default_factory=dict)
    cover_url: str = ""
    duration_ms: int = 0
    fee: int = 0


class MusicProvider(ABC):
    """音乐数据源 Provider 抽象基类。

    所有音乐源必须实现 search() 和 health_check()。
    support_account=False：默认不支持账号。需登录的 Provider 重写为 True。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 唯一标识，如 'netease' / 'qqmusic'。"""

    @property
    def support_account(self) -> bool:
        """是否支持登录账号状态查询。

        子类重写为 True 后，ProviderAccountService 会定期调用 get_account_status()。
        """
        return False

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[ProviderSearchResult]:
        """搜索歌曲，返回归一化结果列表。失败返回空列表（故障隔离）。"""

    @abstractmethod
    async def get_play_url(self, source: SongSource) -> str | None:
        """获取可播放 URL。参数统一为 SongSource，返回 URL 或 None。"""

    async def get_playlist_tracks(self, playlist_id: str) -> list[ProviderSearchResult]:
        """获取歌单歌曲列表。

        非 abstractmethod，默认返回 []（故障隔离）。
        支持歌单的 Provider 重写此方法。
        """
        return []

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查。True=可用，False=不可用。"""
