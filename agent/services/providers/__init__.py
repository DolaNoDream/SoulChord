"""Provider 包 — 多音乐源（v9.14）。"""

from agent.services.providers.base import MusicProvider, ProviderSearchResult, SongSource
from agent.services.providers.registry import ProviderRegistry, create_providers
from agent.services.providers.netease_provider import NeteaseProvider
from agent.services.providers.qq_provider import QQProvider

__all__ = [
    "MusicProvider",
    "ProviderSearchResult",
    "SongSource",
    "ProviderRegistry",
    "create_providers",
    "NeteaseProvider",
    "QQProvider",
]
