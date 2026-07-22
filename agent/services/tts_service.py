"""TTSService — 语音合成服务（Fish Audio 同步 HTTP API）。

★ 调用 Fish Audio POST /v1/tts 合成音频
★ 音频缓存到 data/tts/，通过 /api/tts/audio/{filename} 暴露
★ API Key 缺失时静默降级返回空（不崩溃）

Fish Audio API 文档：
  - POST https://api.fish.audio/v1/tts
  - Header model: s2.1-pro / s2.1-pro-free（免费测试）
  - Body: {text, reference_id, format, prosody: {speed}}
"""

import hashlib
import logging
import os
import time

import httpx

from agent.config import settings as _settings

logger = logging.getLogger(__name__)

# TTS 文件缓存目录
_TTS_DIR = os.path.join(_settings.DATA_DIR, "tts")

# Fish Audio 推荐模型
_FISH_TTS_MODEL = "s2.1-pro-free"  # Fish Audio 免费开发模型（$0）


def _tts_audio_url(filename: str) -> str:
    """构造 TTS 音频的绝对 URL（带 Agent 端口），前端可直接播放。"""
    return f"http://localhost:{_settings.AGENT_PORT}/api/tts/audio/{filename}"


class TTSService:
    """语音合成服务（Fish Audio）。

    调用 Fish Audio 同步 TTS API 生成 MP3 音频，
    缓存到本地 data/tts/，返回可代理访问的 URL。
    """

    async def synthesize(self, text: str, voice_id: str | None = None) -> dict:
        """文本转语音。

        Args:
            text: 要合成的文本
            voice_id: 音色 ID（Fish Audio 文档中为 reference_id），
                      默认使用配置的 FISH_AUDIO_VOICE_ID

        Returns:
            dict: {
                "audio_url": str,       # 可播放的音频 URL（空字符串表示失败/降级）
                "duration_ms": int,     # 预估时长（毫秒）
                "provider": str,        # "fish_audio" / "fish_audio_mock"
            }
        """
        if not text or not text.strip():
            logger.warning("TTSService.synthesize: empty text")
            return {"audio_url": "", "duration_ms": 0, "provider": "fish_audio_mock"}

        api_key = _settings.FISH_AUDIO_API_KEY
        if not api_key:
            logger.warning("TTSService.synthesize: FISH_AUDIO_API_KEY not configured, "
                           "returning empty (text_len=%d)", len(text))
            return {"audio_url": "", "duration_ms": 0, "provider": "fish_audio_mock"}

        # 估算时长（秒），约 4 字/秒，最少 1 秒
        estimated_duration_ms = max(1000, len(text.strip()) * 250)

        # 生成缓存文件名
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        ts = int(time.time() * 1000)
        filename = f"{text_hash}_{ts}.mp3"
        filepath = os.path.join(_TTS_DIR, filename)

        # 已缓存则直接返回
        if os.path.isfile(filepath):
            logger.info("TTSService.synthesize: cache hit for text_hash=%s", text_hash)
            return {
                "audio_url": _tts_audio_url(filename),
                "duration_ms": estimated_duration_ms,
                "provider": "fish_audio",
            }

        # 调用 Fish Audio 同步 TTS API（文档 v1）
        #   POST https://api.fish.audio/v1/tts
        #   Header: Authorization: Bearer {key}
        #   Header: model: s2.1-pro-free
        #   Body: {text, reference_id, format, prosody: {speed}}
        voice_id = voice_id or _settings.FISH_AUDIO_VOICE_ID
        url = "https://api.fish.audio/v1/tts"

        try:
            os.makedirs(_TTS_DIR, exist_ok=True)

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "model": _FISH_TTS_MODEL,
                    },
                    json={
                        "text": text,
                        "reference_id": voice_id,
                        "format": "mp3",
                        "prosody": {"speed": 1.0},
                    },
                )

            if resp.status_code != 200:
                logger.error("TTSService.synthesize: Fish Audio API error "
                             "status=%d body=%.200s", resp.status_code, resp.text[:200])
                return {
                    "audio_url": "",
                    "duration_ms": estimated_duration_ms,
                    "provider": "fish_audio_mock",
                }

            # 保存音频文件
            with open(filepath, "wb") as f:
                f.write(resp.content)

            actual_size_kb = len(resp.content) / 1024
            logger.info("TTSService.synthesize: OK text_len=%d → %s (%.1fKB)",
                        len(text), filename, actual_size_kb)

            return {
                "audio_url": _tts_audio_url(filename),
                "duration_ms": estimated_duration_ms,
                "provider": "fish_audio",
            }

        except httpx.TimeoutException:
            logger.error("TTSService.synthesize: timeout after 30s (text_len=%d)", len(text))
            return {"audio_url": "", "duration_ms": estimated_duration_ms, "provider": "fish_audio_mock"}
        except httpx.RequestError as e:
            logger.error("TTSService.synthesize: request failed: %s", e)
            return {"audio_url": "", "duration_ms": estimated_duration_ms, "provider": "fish_audio_mock"}
        except OSError as e:
            logger.error("TTSService.synthesize: file IO error: %s", e)
            return {"audio_url": "", "duration_ms": estimated_duration_ms, "provider": "fish_audio_mock"}


# 模块级单例
tts_service = TTSService()
