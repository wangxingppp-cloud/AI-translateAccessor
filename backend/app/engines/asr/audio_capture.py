"""
Windows WASAPI Loopback Capture via raw ctypes + COM.

Directly calls Windows Core Audio API (mmdevapi.dll) for loopback capture.
No PortAudio, no comtypes gen — pure ctypes.
"""
import asyncio
import ctypes
from ctypes import wintypes, byref, POINTER, sizeof, cast
from threading import Thread
from typing import Callable, Optional
import numpy as np
from loguru import logger

TARGET_RATE = 16000

# COM stuff
import uuid as _uuid

CLSCTX_ALL = 23
COINIT_MULTITHREADED = 0

def _guid_bytes(s: str) -> bytes:
    """Convert GUID string to 16-byte LE representation."""
    return _uuid.UUID(s).bytes_le

IID_MMDeviceEnumerator = _guid_bytes("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioClient = _guid_bytes("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2")
IID_IAudioCaptureClient = _guid_bytes("C8ADBD64-E71E-48A0-A4DE-185C395CD317")
CLSID_MMDeviceEnumerator = _guid_bytes("BCDE0395-E52F-467C-8E3D-C4579291692E")


class SystemAudioCapture:
    """WASAPI loopback capture via ctypes COM."""

    def __init__(self):
        self._running = False
        self._chunk_callback: Optional[Callable] = None
        self._loop = None

    def start(self, on_chunk: Callable) -> None:
        self._chunk_callback = on_chunk
        self._running = True
        self._loop = asyncio.get_event_loop()
        Thread(target=self._capture_thread, daemon=True).start()
        logger.info("WASAPI loopback capture started (ctypes COM)")

    def stop(self) -> None:
        self._running = False

    def _capture_thread(self) -> None:
        ole32 = ctypes.windll.ole32
        ole32.CoInitializeEx(None, COINIT_MULTITHREADED)

        try:
            # GUID ctypes structure
            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            def make_guid(b: bytes) -> GUID:
                return GUID(
                    int.from_bytes(b[:4], 'little'),
                    int.from_bytes(b[4:6], 'little'),
                    int.from_bytes(b[6:8], 'little'),
                    (ctypes.c_ubyte * 8)(*b[8:16]),
                )

            clsid = make_guid(CLSID_MMDeviceEnumerator)
            iid_de = make_guid(IID_MMDeviceEnumerator)
            iid_ac = make_guid(IID_IAudioClient)
            iid_cc = make_guid(IID_IAudioCaptureClient)

            # Create MMDeviceEnumerator COM object
            pUnknown = ctypes.c_void_p()
            hr = ole32.CoCreateInstance(
                ctypes.byref(clsid), None, CLSCTX_ALL,
                ctypes.byref(iid_de), ctypes.byref(pUnknown))
            if hr != 0:
                raise OSError(f"CoCreateInstance failed: {hr:#x}")

            # Get IMMDeviceEnumerator vtable
            vtbl = cast(pUnknown, POINTER(POINTER(ctypes.c_void_p))).contents

            # GetDefaultAudioEndpoint(EDataFlow=0, ERole=0, &device)
            GetDefaultAudioEndpoint = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                POINTER(ctypes.c_void_p))
            fn = cast(vtbl[4], GetDefaultAudioEndpoint)
            pDevice = ctypes.c_void_p()
            fn(pUnknown, 0, 0, byref(pDevice))  # eRender, eConsole

            # IMMDevice::Activate(IID_IAudioClient, CLSCTX_ALL, NULL, &pAC)
            device_vtbl = cast(pDevice, POINTER(POINTER(ctypes.c_void_p))).contents
            Activate = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p,
                ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                POINTER(ctypes.c_void_p))
            fn_act = cast(device_vtbl[3], Activate)
            pAC = ctypes.c_void_p()
            fn_act(pDevice, ctypes.byref(iid_ac), CLSCTX_ALL, None, byref(pAC))

            # IAudioClient::GetMixFormat
            ac_vtbl = cast(pAC, POINTER(POINTER(ctypes.c_void_p))).contents
            GetMixFormat = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p, POINTER(ctypes.c_void_p))
            fn_mf = cast(ac_vtbl[8], GetMixFormat)
            pFmt = ctypes.c_void_p()
            fn_mf(pAC, byref(pFmt))

            # Read WAVEFORMATEX
            class WAVEFORMATEX(ctypes.Structure):
                _fields_ = [
                    ("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
                    ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
                    ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                    ("cbSize", wintypes.WORD),
                ]
            fmt = cast(pFmt, POINTER(WAVEFORMATEX)).contents
            device_rate = fmt.nSamplesPerSec
            device_ch = fmt.nChannels
            device_bits = fmt.wBitsPerSample
            frame_size = fmt.nBlockAlign

            logger.info(f"WASAPI: {device_rate}Hz {device_ch}ch {device_bits}bit")

            # IAudioClient::Initialize(SHARED, LOOPBACK, 1s, 0, format, NULL)
            Initialize = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p,
                ctypes.c_int, wintypes.DWORD, ctypes.c_longlong, ctypes.c_longlong,
                ctypes.c_void_p, ctypes.c_void_p)
            fn_init = cast(ac_vtbl[3], Initialize)
            fn_init(pAC, 0, 0x00020000, 10_000_000, 0, pFmt, None)
            ole32.CoTaskMemFree(pFmt)

            # IAudioClient::GetService(IID_IAudioCaptureClient, &pCC)
            GetService = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, POINTER(ctypes.c_void_p))
            fn_gs = cast(ac_vtbl[14], GetService)
            pCC = ctypes.c_void_p()
            fn_gs(pAC, ctypes.byref(iid_cc), byref(pCC))

            # IAudioClient::Start
            Start = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
            cast(ac_vtbl[10], Start)(pAC)

            # IAudioCaptureClient vtable (3=IUnknown)
            # Index 3: GetBuffer, 4: ReleaseBuffer, 5: GetNextPacketSize
            cc_vtbl = cast(pCC, POINTER(POINTER(ctypes.c_void_p))).contents

            GetBuffer = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p,
                POINTER(ctypes.c_void_p), POINTER(wintypes.DWORD), POINTER(wintypes.DWORD),
                POINTER(ctypes.c_longlong), POINTER(ctypes.c_longlong))
            fn_gb = cast(cc_vtbl[3], GetBuffer)

            ReleaseBuffer = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
            fn_rb = cast(cc_vtbl[4], ReleaseBuffer)

            GetNextPacketSize = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p, POINTER(wintypes.DWORD))
            fn_gnps = cast(cc_vtbl[5], GetNextPacketSize)

            # Main capture loop
            ratio = TARGET_RATE / device_rate

            _pkts = 0
            _silent = 0
            while self._running:
                packet_size = wintypes.DWORD()
                fn_gnps(pCC, byref(packet_size))
                if packet_size.value == 0:
                    _silent += 1
                    if _silent % 200 == 0:
                        logger.debug(f"WASAPI: no packets for {_silent*5}ms")
                    import time; time.sleep(0.005)
                    continue
                _pkts += 1
                _silent = 0

                pData = ctypes.c_void_p()
                frames = wintypes.DWORD()
                flags = wintypes.DWORD()
                fn_gb(pCC, byref(pData), byref(frames), byref(flags), None, None)

                if frames.value > 0:
                    nf = frames.value
                    buf_size = nf * frame_size
                    buf = (ctypes.c_byte * buf_size)()
                    ctypes.memmove(buf, pData, buf_size)

                    # Convert to float32
                    if device_bits == 32:
                        audio = np.frombuffer(bytearray(buf), dtype=np.float32).reshape(nf, device_ch)
                    else:
                        audio = np.frombuffer(bytearray(buf), dtype=np.int16).astype(np.float32).reshape(nf, device_ch) / 32768.0

                    mono = audio[:, :min(device_ch, 2)].mean(axis=1)

                    if device_rate != TARGET_RATE and len(mono) > 1:
                        n_out = max(1, int(len(mono) * ratio))
                        idx = np.linspace(0, len(mono) - 1, n_out)
                        lo = np.floor(idx).astype(int)
                        hi = np.clip(lo + 1, 0, len(mono) - 1)
                        mono = mono[lo] * (1 - (idx - lo)) + mono[hi] * (idx - lo)

                    pcm = (np.clip(mono, -1, 1) * 32767).astype(np.int16).tobytes()
                    if _pkts == 1:
                        logger.info(f"[CAPTURE] First packet: {len(pcm)} bytes, calling callback")
                    if self._chunk_callback and self._loop:
                        self._loop.call_soon_threadsafe(self._chunk_callback, pcm)
                        if _pkts <= 3:
                            logger.info(f"[CAPTURE] Packet #{_pkts} sent to callback")

                fn_rb(pCC, frames.value)

            Stop = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
            cast(ac_vtbl[11], Stop)(pAC)

        except Exception as e:
            logger.error(f"WASAPI capture error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            ole32.CoUninitialize()


_capture: Optional[SystemAudioCapture] = None


def get_audio_capture() -> SystemAudioCapture:
    global _capture
    if _capture is None:
        _capture = SystemAudioCapture()
    return _capture
