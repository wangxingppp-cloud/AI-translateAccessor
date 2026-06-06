"""
Cloud ASR engines — iFlytek & Baidu streaming ASR via WebSocket.

Both implement the same StreamingASR interface used by ws.py.
Audio chunks are forwarded to the cloud API and results streamed back.
"""
import asyncio
import hashlib
import hmac
import base64
import time
import json
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional
from urllib.parse import urlencode

import websockets
from loguru import logger

from .sherpa_engine import ASRResult


@dataclass
class AsrEngineConfig:
    """Configuration passed from frontend ASR settings."""
    provider: str = "local"       # local | iflytek | baidu
    api_key: str = ""
    api_secret: str = ""          # iFlytek/Baidu AppSecret
    app_id: str = ""              # iFlytek AppID
    base_url: str = ""


class StreamingASR:
    """Base interface for streaming ASR engines."""

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        raise NotImplementedError


class IFlytekASR(StreamingASR):
    """
    iFlytek Real-time ASR (Xunfei) via WebSocket.

    API docs: https://www.xfyun.cn/doc/asr/rtasr/API.html
    WebSocket: wss://rtasr.xfyun.cn/v1/ws

    Auth: HMAC-SHA1 signature with apiKey + timestamp.
    Send: binary PCM (16kHz, 16bit, mono).
    Receive: JSON with "action" field.
    """

    WS_URL = "wss://rtasr.xfyun.cn/v1/ws"

    def __init__(self, config: AsrEngineConfig):
        self._app_id = config.app_id
        self._api_key = config.api_key
        self._api_secret = config.api_secret
        self._ws_url = config.base_url or self.WS_URL
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False

    async def _connect(self) -> bool:
        """Build signed WebSocket URL and connect."""
        ts = str(int(time.time()))
        sign_raw = f"{self._api_key}{ts}"
        signa = hmac.new(
            self._api_secret.encode(),
            sign_raw.encode(),
            hashlib.sha1,
        ).digest()
        signa = base64.b64encode(signa).decode()

        params = urlencode({
            "appid": self._app_id,
            "ts": ts,
            "signa": signa,
            "lang": "en",       # Language: cn|en
            "punc": "1",         # Punctuation on
            "format": "pcm",    # Audio format
            "rate": "16000",    # Sample rate
            "channel": "1",     # Mono
        })
        url = f"{self._ws_url}?{params}"

        try:
            self._ws = await websockets.connect(url, ping_interval=30)
            self._connected = True
            logger.info("iFlytek ASR connected")
            return True
        except Exception as e:
            logger.error(f"iFlytek connection failed: {e}")
            return False

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        if not self._connected:
            if not await self._connect():
                return

        if self._ws is None:
            return

        try:
            # Send audio chunk as binary
            await self._ws.send(pcm_bytes)

            # Check for results (non-blocking)
            try:
                resp = await asyncio.wait_for(self._ws.recv(), timeout=0.1)
                data = json.loads(resp)

                action = data.get("action", "")
                if action == "result":
                    # {"action":"result","data":"{\"cn\":{\"st\":{\"type\":\"1\",\"rt\":[{\"ws\":[{\"cw\":[{\"w\":\"hello\"}],\"wb\":0}]}]}}}"}
                    result_data = json.loads(data.get("data", "{}"))
                    text = self._parse_result(result_data)
                    if text:
                        yield ASRResult(text=text, is_final=False, timestamp=time.time())
                elif action == "error":
                    logger.warning(f"iFlytek error: {data}")
            except asyncio.TimeoutError:
                pass  # No result yet

        except websockets.ConnectionClosed:
            logger.info("iFlytek connection closed")
            self._connected = False
            self._ws = None

    def _parse_result(self, data: dict) -> str:
        """Parse iFlytek JSON result into text."""
        try:
            cn = data.get("cn", {})
            st = cn.get("st", {})
            rt = st.get("rt", [])
            words = []
            for segment in rt:
                for ws_item in segment.get("ws", []):
                    for cw in ws_item.get("cw", []):
                        w = cw.get("w", "")
                        if w:
                            words.append(w)
            return "".join(words)
        except Exception:
            return ""

    async def close(self):
        if self._ws:
            await self._ws.close()
            self._ws = None
            self._connected = False


class BaiduASR(StreamingASR):
    """
    Baidu Real-time ASR via WebSocket.

    API docs: https://ai.baidu.com/ai-doc/SPEECH/Vk38lxily
    WebSocket: wss://vop.baidu.com/realtime_asr

    Auth: Access token obtained via OAuth with API Key + Secret Key.
    Send: binary PCM (16kHz, 16bit, mono).
    Receive: JSON with "type" field.
    """

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    WS_URL = "wss://vop.baidu.com/realtime_asr"

    def __init__(self, config: AsrEngineConfig):
        self._api_key = config.api_key
        self._api_secret = config.api_secret
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._token: Optional[str] = None
        self._connected = False

    async def _get_token(self) -> Optional[str]:
        """OAuth token for Baidu API."""
        import aiohttp
        params = {
            "grant_type": "client_credentials",
            "client_id": self._api_key,
            "client_secret": self._api_secret,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.TOKEN_URL, params=params) as resp:
                    data = await resp.json()
                    return data.get("access_token")
        except Exception as e:
            logger.error(f"Baidu token failed: {e}")
            return None

    async def _connect(self) -> bool:
        if not self._token:
            self._token = await self._get_token()
            if not self._token:
                return False

        url = f"{self.WS_URL}?access_token={self._token}"

        try:
            # Send start frame
            self._ws = await websockets.connect(url, ping_interval=30)
            start = json.dumps({
                "type": "START",
                "data": {
                    "appid": self._api_key,
                    "format": "pcm",
                    "rate": 16000,
                    "channel": 1,
                    "cuid": "ai-translate",
                    "token": self._token,
                    "dev_pid": 1737,  # English model
                }
            })
            await self._ws.send(start)
            resp = await self._ws.recv()
            data = json.loads(resp)
            if data.get("type") == "START":
                self._connected = True
                logger.info("Baidu ASR connected")
                return True
            else:
                logger.warning(f"Baidu START failed: {data}")
                return False
        except Exception as e:
            logger.error(f"Baidu connection failed: {e}")
            return False

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        if not self._connected:
            if not await self._connect():
                return

        if self._ws is None:
            return

        try:
            # Send audio data frame
            data_frame = json.dumps({
                "type": "DATA",
                "data": base64.b64encode(pcm_bytes).decode(),
            })
            await self._ws.send(data_frame)

            # Check for results
            try:
                resp = await asyncio.wait_for(self._ws.recv(), timeout=0.1)
                msg = json.loads(resp)
                msg_type = msg.get("type", "")
                if msg_type == "FINALS" or msg_type == "PARTIALS":
                    text = msg.get("data", {}).get("result", "")
                    if text:
                        yield ASRResult(
                            text=text,
                            is_final=msg_type == "FINALS",
                            timestamp=time.time(),
                        )
                elif msg_type == "ERROR":
                    logger.warning(f"Baidu error: {msg}")
            except asyncio.TimeoutError:
                pass

        except websockets.ConnectionClosed:
            logger.info("Baidu connection closed")
            self._connected = False
            self._ws = None

    async def close(self):
        if self._ws:
            try:
                await self._ws.send(json.dumps({"type": "FINISH"}))
            except Exception:
                pass
            await self._ws.close()
            self._ws = None
            self._connected = False


def create_cloud_asr(config: AsrEngineConfig) -> StreamingASR:
    """Factory for cloud ASR engines."""
    if config.provider == "iflytek":
        return IFlytekASR(config)
    elif config.provider == "baidu":
        return BaiduASR(config)
    else:
        raise ValueError(f"Unknown ASR provider: {config.provider}")
