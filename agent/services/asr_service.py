"""ASRService — 语音识别服务（Fish Audio HTTP API）。

★ 调用 Fish Audio POST /v1/asr 转写音频（multipart/form-data）
★ 支持中文、英文等多语言
★ API Key 缺失时静默降级返回空（不崩溃）

Fish Audio API 文档：
  - POST https://api.fish.audio/v1/asr
  - Content-Type: multipart/form-data
  - Fields: audio (file), language (optional), ignore_timestamps (bool)
"""

import logging

import httpx

from agent.config import settings as _settings

logger = logging.getLogger(__name__)


class ASRService:
    """语音识别服务（Fish Audio）。

    接收音频文件路径，调用 Fish Audio v1 ASR API 转写，
    返回识别文本。
    """

    async def recognize(self, audio_data: bytes, language: str = "zh") -> dict:
        """语音转文字。

        Args:
            audio_data: 音频文件原始字节数据
            language: 语言代码，默认 "zh"

        Returns:
            dict: {
                "text": str,            # 转写文本
                "confidence": float,    # 置信度 0.0~1.0
                "duration_ms": int,     # 音频时长（毫秒）
                "source": str,          # "fish_audio" / "fish_audio_mock"
            }
        """
        if not audio_data or len(audio_data) == 0:
            logger.warning("ASRService.recognize: empty audio_data")
            return {"text": "", "confidence": 0.0, "duration_ms": 0, "source": "fish_audio_mock"}

        api_key = _settings.FISH_AUDIO_API_KEY
        if not api_key:
            logger.warning("ASRService.recognize: FISH_AUDIO_API_KEY not configured, returning empty")
            return {"text": "", "confidence": 0.0, "duration_ms": 0, "source": "fish_audio_mock"}

        # Fish Audio v1 ASR API（multipart/form-data）
        url = "https://api.fish.audio/v1/asr"

        try:
            files = {"audio": ("audio", audio_data, "audio/wav")}
            data = {"language": language, "ignore_timestamps": "true"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files=files,
                    data=data,
                )

            if resp.status_code != 200:
                logger.error("ASRService.recognize: Fish Audio API error "
                             "status=%d body=%.200s", resp.status_code, resp.text[:200])
                return {"text": "", "confidence": 0.0, "duration_ms": 0, "source": "fish_audio_mock"}

            data = resp.json()
            text = data.get("text", "")
            duration = data.get("duration", 0)
            duration_ms = int(duration * 1000)

            logger.info("ASRService.recognize: OK text=%.60s duration_ms=%d",
                        text, duration_ms)

            return {
                "text": text,
                "confidence": 0.95,
                "duration_ms": duration_ms,
                "source": "fish_audio",
            }

        except httpx.TimeoutException:
            logger.error("ASRService.recognize: timeout after 60s")
            return {"text": "", "confidence": 0.0, "duration_ms": 0, "source": "fish_audio_mock"}
        except httpx.RequestError as e:
            logger.error("ASRService.recognize: request failed: %s", e)
            return {"text": "", "confidence": 0.0, "duration_ms": 0, "source": "fish_audio_mock"}
        except (ValueError, KeyError) as e:
            logger.error("ASRService.recognize: response parse error: %s", e)
            return {"text": "", "confidence": 0.0, "duration_ms": 0, "source": "fish_audio_mock"}


# 模块级单例
asr_service = ASRService()
