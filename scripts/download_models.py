"""
Download AI Simultaneous Interpretation models.

Usage: python scripts/download_models.py [asr|vad|nmt|all]

Models:
  asr-streaming — Zipformer English streaming (~100MB) — real-time, <300ms latency
  asr-offline   — SenseVoice multilingual offline (~230MB) — batch, 2-5s latency
  vad           — Silero VAD (~0.6MB)
  nmt           — opus-mt-en-zh ONNX (~430MB) — local EN→ZH translation
"""
import urllib.request
import tarfile
import shutil
import sys
from pathlib import Path

MODELS = {
    "asr-streaming": {
        "url": (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "asr-models/sherpa-onnx-streaming-zipformer-en-2023-06-26.tar.bz2"
        ),
        "name": "sherpa-onnx-streaming-zipformer-en-2023-06-26",
        "dest": "sherpa-onnx-paraformer",  # Overwrites offline model with streaming
        "desc": "Zipformer English Streaming ASR (real-time, low latency)",
    },
    "asr-offline": {
        "url": (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2"
        ),
        "name": "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
        "dest": "sherpa-onnx-sensevoice",
        "desc": "SenseVoice Multilingual Offline ASR (zh/en/ja/ko/yue)",
    },
    "vad": {
        "url": (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "asr-models/silero_vad.onnx"
        ),
        "name": "silero_vad.onnx",
        "dest": "silero-vad",
        "desc": "Silero VAD",
    },
}

DEFAULT = "asr-streaming"

NMT_REPO = "R4kSo1997/opus-mt-en-zh-onnx-int8"


def download_nmt(models_dir: Path) -> None:
    """Download opus-mt-en-zh ONNX model from Hugging Face."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)

    dest = models_dir / "nmt-en-zh"
    print(f"\n[NMT EN→ZH Translation]")
    print(f"  Repo: {NMT_REPO}")
    print(f"  Dest: {dest}")
    print(f"  Downloading...")

    snapshot_download(
        repo_id=NMT_REPO,
        local_dir=str(dest),
        local_dir_use_symlinks=False,
    )

    # Only keep the ONNX files we actually use (encoder + decoder)
    onnx_dir = dest / "onnx"
    if onnx_dir.exists():
        keep = {"encoder_model.onnx", "decoder_model.onnx"}
        for f in onnx_dir.iterdir():
            if f.name not in keep:
                size_mb = f.stat().st_size / (1024 * 1024)
                f.unlink()
                print(f"  Removed unused: {f.name} ({size_mb:.0f}MB)")

    files = list(dest.glob("*"))
    print(f"  Installed {len(files)} files to {dest}")


def download(url: str, dest: Path, desc: str) -> None:
    print(f"  Downloading {desc}...")
    def report(count, block_size, total_size):
        pct = int(count * block_size * 100 / total_size) if total_size > 0 else 0
        mb = count * block_size / (1024 * 1024)
        sys.stdout.write(f"\r    {mb:.0f}MB ({pct}%)")
        sys.stdout.flush()
    urllib.request.urlretrieve(url, dest, reporthook=report)
    print("\r    Done.          ")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    key = args[0] if args else DEFAULT

    models_dir = Path(__file__).resolve().parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    # Handle NMT separately (uses huggingface_hub, not direct URL)
    if key == "nmt":
        download_nmt(models_dir)
        print("\nDone.")
        return
    if key == "all":
        keys = list(MODELS.keys())
        download_nmt(models_dir)
    elif key in MODELS:
        keys = [key]
    else:
        print(f"Unknown model: {key}. Available: {list(MODELS.keys()) + ['nmt']}")
        sys.exit(1)

    for k in keys:
        info = MODELS[k]
        dest_dir = models_dir / info["dest"]
        dl_path = models_dir / info["name"]

        if k == "vad" and dest_dir.exists() and list(dest_dir.glob("*.onnx")):
            print(f"\n[{info['desc']}] Already installed at {dest_dir}")
            continue

        print(f"\n[{info['desc']}]")

        if dl_path.suffix == '.onnx':
            if not dl_path.exists():
                download(info["url"], dl_path, info["desc"])
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            dest_dir.mkdir(parents=True)
            shutil.copy2(dl_path, dest_dir / dl_path.name)
            dl_path.unlink(missing_ok=True)
        else:
            tar_path = models_dir / f"{info['name']}.tar.bz2"
            if not tar_path.exists():
                download(info["url"], tar_path, info["desc"])
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            print("  Extracting...")
            with tarfile.open(tar_path, "r:bz2") as tar:
                tar.extractall(path=models_dir)
            extracted = models_dir / info["name"]
            if extracted.exists() and extracted != dest_dir:
                extracted.rename(dest_dir)
            tar_path.unlink(missing_ok=True)

        files = list(dest_dir.glob("*"))
        print(f"  Installed {len(files)} files to {dest_dir}")

    # Cleanup: remove large full-precision models if INT8 exists
    for d in models_dir.glob("sherpa-onnx-*"):
        full = d / "model.onnx"
        int8 = d / "model.int8.onnx"
        if full.exists() and int8.exists():
            size_mb = full.stat().st_size / (1024*1024)
            full.unlink()
            print(f"\nRemoved {d.name}/model.onnx ({size_mb:.0f}MB), using INT8")

    print("\nDone.")


if __name__ == "__main__":
    main()
