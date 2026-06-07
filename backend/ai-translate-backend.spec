# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('app', 'app')]
binaries = []
hiddenimports = [
    # Core framework
    'fastapi',
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'websockets',
    # ASR / Audio
    'sherpa_onnx',
    'onnxruntime',
    'numpy',
    'soundfile',
    'sentencepiece',
    # NMT
    'transformers',
    'huggingface_hub',
    # LLM
    'openai',
    'anthropic',
    # TTS
    'edge_tts',
    # Data / Config
    'pydantic',
    'pydantic_settings',
    'pydantic.deprecated',
    'sqlalchemy',
    'sqlalchemy.dialects',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.ext',
    'sqlalchemy.ext.asyncio',
    # Logging
    'loguru',
    # Platform
    'platformdirs',
    # Windows COM (WASAPI)
    'comtypes',
]
tmp_ret = collect_all('aiosqlite')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ai-translate-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
