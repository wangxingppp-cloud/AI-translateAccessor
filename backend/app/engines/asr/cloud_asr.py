"""
Cloud ASR engines — iFlytek RTASR / IAT & Baidu streaming ASR via WebSocket.
"""
import asyncio
import hashlib
import hmac
import base64
import time
import json
import uuid as _uuid
from typing import AsyncGenerator, Optional
from urllib.parse import urlencode, quote, urlparse
from dataclasses import dataclass

import websockets
from loguru import logger
from .sherpa_engine import ASRResult


@dataclass
class AsrEngineConfig:
    provider: str = "local"
    api_key: str = ""
    api_secret: str = ""
    app_id: str = ""
    base_url: str = ""


class StreamingASR:
    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# iFlytek Real-Time ASR (RTASR) — 实时语音转写大模型
# Protocol doc: wss://office-api-ast-dx.iflyaisol.com/ast/communicate/v1
# ---------------------------------------------------------------------------

class IFlytekRTASR(StreamingASR):
    """
    iFlytek Real-Time Speech Transcription (实时语音转写大模型).

    Endpoint: wss://office-api-ast-dx.iflyaisol.com/ast/communicate/v1
    Auth: HmacSHA1(accessKeySecret, sortedBaseString) → Base64
    Send: raw binary PCM chunks (1280 bytes / 40ms)
    Receive: background task pushes results into asyncio.Queue
    """

    DEFAULT_URL = "wss://office-api-ast-dx.iflyaisol.com/ast/communicate/v1"
    FRAME_SIZE = 1280  # bytes per frame (40ms @ 16kHz 16bit)

    def __init__(self, config: AsrEngineConfig):
        self._app_id = config.app_id
        self._api_key = config.api_key
        self._api_secret = config.api_secret
        self._base_url = config.base_url or self.DEFAULT_URL
        if "iflyaisol.com" in self._base_url and "/ast/" not in self._base_url:
            self._base_url = self.DEFAULT_URL
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._connecting = False
        self._connect_lock: Optional[asyncio.Lock] = None
        self._send_lock: Optional[asyncio.Lock] = None
        self._recv_lock: Optional[asyncio.Lock] = None
        self._buffer = b""
        self._session_id: Optional[str] = None

    def _build_url(self) -> str:
        utc = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        if not utc or utc[-5] not in "+-":
            offset = time.timezone if time.daylight == 0 else time.altzone
            sign = "-" if offset > 0 else "+"
            offset = abs(offset)
            utc = time.strftime(f"%Y-%m-%dT%H:%M:%S{sign}{offset // 3600:02d}{offset % 3600 // 60:02d}")

        params = {
            "accessKeyId": self._api_key,
            "appId": self._app_id,
            "uuid": _uuid.uuid4().hex,
            "utc": utc,
            "audio_encode": "pcm_s16le",
            "lang": "autodialect",
            "samplerate": "16000",
        }
        sorted_params = sorted(params.items())
        base_string = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_params)
        signature = base64.b64encode(
            hmac.new(self._api_secret.encode(), base_string.encode(), hashlib.sha1).digest()
        ).decode()
        full_qs = f"{base_string}&{quote('signature', safe='')}={quote(signature, safe='')}"
        return f"{self._base_url}?{full_qs}"

    async def _connect(self) -> bool:
        if self._connecting:
            return False
        if self._connect_lock is None:
            self._connect_lock = asyncio.Lock()
        async with self._connect_lock:
            if self._connected and self._ws:
                return True
            self._connecting = True
            try:
                url = self._build_url()
                logger.info(f"IFlytek RTASR connecting: {url.split('?')[0]}")
                self._ws = await websockets.connect(url, ping_interval=30)
                greeting = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
                msg = json.loads(greeting)
                logger.info(f"IFlytek RTASR greeting: {greeting[:500]}")
                data = msg.get("data", {})
                action = data.get("action", "") if isinstance(data, dict) else ""
                if action == "started":
                    self._session_id = data.get("sessionId", "")
                    self._connected = True
                    self._send_lock = asyncio.Lock()
                    self._recv_lock = asyncio.Lock()
                    logger.info(f"IFlytek RTASR started, sessionId={self._session_id}")
                    return True
                else:
                    code = msg.get("code", data.get("code", "?"))
                    desc = msg.get("desc", data.get("desc", ""))
                    logger.error(f"IFlytek RTASR handshake failed: action={action} code={code} desc={desc}")
                    await self._ws.close()
                    self._ws = None
                    return False
            except asyncio.TimeoutError:
                logger.error("IFlytek RTASR handshake timeout")
                if self._ws:
                    await self._ws.close()
                    self._ws = None
                return False
            except Exception as e:
                logger.error(f"IFlytek RTASR connection failed: {e}")
                self._ws = None
                return False
            finally:
                self._connecting = False

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        logger.info(f"RTASR process_chunk enter: connected={self._connected} ws={self._ws is not None} pcm={len(pcm_bytes)}B")
        if not self._connected and not await self._connect():
            logger.warning("RTASR process_chunk: connect failed, returning")
            return
        if self._ws is None:
            logger.warning("RTASR process_chunk: ws is None after connect")
            return

        self._buffer += pcm_bytes
        logger.info(f"RTASR buffer={len(self._buffer)}B")

        try:
            # Send buffered frames (under send lock)
            if self._send_lock is None:
                self._send_lock = asyncio.Lock()
            async with self._send_lock:
                frames_sent = 0
                while len(self._buffer) >= self.FRAME_SIZE:
                    frame = self._buffer[:self.FRAME_SIZE]
                    self._buffer = self._buffer[self.FRAME_SIZE:]
                    await self._ws.send(frame)
                    frames_sent += 1
                if frames_sent > 0:
                    logger.info(f"RTASR sent {frames_sent} frames")

            # Receive results (under recv lock, short timeout)
            if self._recv_lock is None:
                self._recv_lock = asyncio.Lock()
            async with self._recv_lock:
                for _ in range(50):
                    try:
                        resp = await asyncio.wait_for(self._ws.recv(), timeout=0.01)
                    except asyncio.TimeoutError:
                        logger.info("RTASR recv timeout (no more data)")
                        break
                    logger.info(f"RTASR raw resp: {resp[:300]}")
                    msg = json.loads(resp)

                    # msg_type is the primary action indicator
                    msg_type = msg.get("msg_type", "")
                    data = msg.get("data")
                    if isinstance(data, dict):
                        action = data.get("action", msg.get("action", msg_type))
                    else:
                        action = msg.get("action", msg_type)
                    code = str(data.get("code", msg.get("code", ""))) if isinstance(data, dict) else str(msg.get("code", ""))
                    desc = data.get("desc", msg.get("desc", "")) if isinstance(data, dict) else msg.get("desc", "")

                    if (action == "result" or msg_type == "result") and code != "error":
                        if data:
                            text = self._parse_result(data)
                            logger.info(f"RTASR result: text='{text}'")
                            if text:
                                is_final = False
                                if isinstance(data, dict):
                                    is_final = data.get("ls", False) or data.get("cn", {}).get("st", {}).get("type", 1) == 0
                                yield ASRResult(text=text, is_final=is_final, timestamp=time.time())
                    elif action == "error" or msg_type == "error":
                        logger.warning(f"RTASR error: code={code} desc={desc}")
                    else:
                        logger.info(f"RTASR msg: msg_type={msg_type} action={action} code={code}")

        except websockets.ConnectionClosed:
            logger.warning("RTASR connection closed")
            self._connected = False
            self._ws = None
        except Exception as e:
            logger.error(f"RTASR process_chunk error: {e}", exc_info=True)

    def _parse_result(self, data) -> str:
        try:
            obj = json.loads(data) if isinstance(data, str) else data
            text_parts = []
            for rt_item in obj.get("cn", {}).get("st", {}).get("rt", []):
                for ws_item in rt_item.get("ws", []):
                    for cw in ws_item.get("cw", []):
                        w = cw.get("w", "")
                        if w:
                            text_parts.append(w)
            return "".join(text_parts)
        except Exception as e:
            logger.debug(f"IFlytek RTASR parse error: {e}")
            return ""

    async def close(self):
        if self._ws and self._connected:
            try:
                end_msg = json.dumps({"end": True, "sessionId": self._session_id or ""})
                logger.info(f"IFlytek RTASR sending end: {end_msg}")
                await self._ws.send(end_msg)
            except Exception:
                pass
            await self._ws.close()
            self._ws = None
            self._connected = False


# ---------------------------------------------------------------------------
# iFlytek IAT (legacy interactive dictation) — older xfyun.cn endpoints
# ---------------------------------------------------------------------------

class IFlytekIAT(StreamingASR):
    """
    iFlytek Voice Dictation (IAT) via WebSocket — legacy API.

    API: wss://iat-api.xfyun.cn/v2/iat
    Auth: MD5(appId + ts + apiKey) in URL params
    Send: JSON frames with base64 PCM
    Receive: JSON frames with recognition results
    """

    WS_URL = "wss://iat-api.xfyun.cn/v2/iat"
    FRAME_SIZE = 1280

    def __init__(self, config: AsrEngineConfig):
        self._app_id = config.app_id
        self._api_key = config.api_key
        self._api_secret = config.api_secret
        self._ws_url = config.base_url or self.WS_URL
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._frame_status = 0
        self._buffer = b""

    async def _connect(self) -> bool:
        ts = str(int(time.time()))
        signa = hashlib.md5(f"{self._app_id}{ts}{self._api_key}".encode()).hexdigest()
        params = urlencode({
            "appid": self._app_id, "ts": ts, "signa": signa,
            "lang": "en", "punc": "1", "format": "pcm",
            "rate": "16000", "channel": "1", "ptt": "1",
        })
        url = f"{self._ws_url}?{params}"
        try:
            self._ws = await websockets.connect(url, ping_interval=30)
            self._connected = True
            self._frame_status = 0
            logger.info(f"IFlytek IAT connected (lang=en)")
            return True
        except Exception as e:
            logger.error(f"IFlytek IAT connection failed: {e}")
            return False

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        if not self._connected and not await self._connect():
            return
        if self._ws is None:
            return
        self._buffer += pcm_bytes
        try:
            while len(self._buffer) >= self.FRAME_SIZE:
                frame = self._buffer[:self.FRAME_SIZE]
                self._buffer = self._buffer[self.FRAME_SIZE:]
                data = {
                    "common": {"app_id": self._app_id},
                    "business": {"language": "en", "domain": "iat", "accent": "mandarin", "ptt": 1},
                    "data": {"status": self._frame_status, "format": "audio/L16;rate=16000",
                             "encoding": "raw", "audio": base64.b64encode(frame).decode()},
                }
                await self._ws.send(json.dumps(data))
                self._frame_status = 1
            try:
                resp = await asyncio.wait_for(self._ws.recv(), timeout=0.1)
                msg = json.loads(resp)
                code = msg.get("code", -1)
                if code == 0 and "data" in msg:
                    result_data = msg["data"]
                    text = self._parse_iat_result(result_data)
                    if text:
                        is_final = result_data.get("status") == 2
                        yield ASRResult(text=text, is_final=is_final, timestamp=time.time())
                elif code != 0:
                    logger.warning(f"IFlytek IAT error code={code}: {msg.get('message', '')}")
            except asyncio.TimeoutError:
                pass
        except websockets.ConnectionClosed:
            logger.info("IFlytek IAT connection closed")
            self._connected = False
            self._ws = None

    def _parse_iat_result(self, data: dict) -> str:
        try:
            result_str = data.get("result", "")
            if not result_str:
                return ""
            result = json.loads(result_str) if isinstance(result_str, str) else result_str
            text_parts = []
            for ws_item in result.get("ws", []):
                for cw in ws_item.get("cw", []):
                    w = cw.get("w", "")
                    if w:
                        text_parts.append(w)
            return "".join(text_parts)
        except Exception:
            return ""

    async def close(self):
        if self._ws and self._connected:
            try:
                if self._buffer:
                    await self._ws.send(json.dumps({
                        "data": {"status": 2, "format": "audio/L16;rate=16000",
                                 "encoding": "raw", "audio": base64.b64encode(self._buffer).decode()},
                    }))
                else:
                    await self._ws.send(json.dumps({"data": {"status": 2}}))
            except Exception:
                pass
            await self._ws.close()
            self._ws = None
            self._connected = False


# ---------------------------------------------------------------------------
# Alias for backward compatibility
# ---------------------------------------------------------------------------

IFlytekASR = IFlytekRTASR


class BaiduASR(StreamingASR):
    """
    Baidu Real-time ASR via WebSocket.

    API: wss://vop.baidu.com/realtime_asr
    Auth: OAuth token via API Key + Secret Key.
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
        import aiohttp
        params = {"grant_type": "client_credentials", "client_id": self._api_key, "client_secret": self._api_secret}
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
        try:
            self._ws = await websockets.connect(f"{self.WS_URL}?access_token={self._token}", ping_interval=30)
            await self._ws.send(json.dumps({"type": "START", "data": {
                "appid": self._api_key, "format": "pcm", "rate": 16000, "channel": 1,
                "cuid": "ai-translate", "token": self._token, "dev_pid": 1737,
            }}))
            resp = json.loads(await self._ws.recv())
            if resp.get("type") == "START":
                self._connected = True
                logger.info("Baidu ASR connected")
                return True
        except Exception as e:
            logger.error(f"Baidu connection failed: {e}")
        return False

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        if not self._connected and not await self._connect():
            return
        try:
            await self._ws.send(json.dumps({"type": "DATA", "data": base64.b64encode(pcm_bytes).decode()}))
            try:
                resp = json.loads(await asyncio.wait_for(self._ws.recv(), timeout=0.1))
                if resp.get("type") in ("FINALS", "PARTIALS"):
                    text = resp.get("data", {}).get("result", "")
                    if text:
                        yield ASRResult(text=text, is_final=resp["type"] == "FINALS", timestamp=time.time())
                elif resp.get("type") == "ERROR":
                    logger.warning(f"Baidu error: {resp}")
            except asyncio.TimeoutError:
                pass
        except websockets.ConnectionClosed:
            self._connected = False
            self._ws = None

    async def close(self):
        if self._ws:
            try: await self._ws.send(json.dumps({"type": "FINISH"}))
            except: pass
            await self._ws.close()
            self._ws = None
            self._connected = False


def create_cloud_asr(config: AsrEngineConfig) -> StreamingASR:
    if config.provider == "iflytek":
        # Use RTASR for newer endpoints (iflyaisol / rtasr), IAT for legacy xfyun.cn
        url = config.base_url or IFlytekRTASR.DEFAULT_URL
        if "iat-api.xfyun.cn" in url:
            return IFlytekIAT(config)
        return IFlytekRTASR(config)
    elif config.provider == "baidu":
        return BaiduASR(config)
    raise ValueError(f"Unknown ASR provider: {config.provider}")
