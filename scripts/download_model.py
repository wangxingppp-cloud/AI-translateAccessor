"""
Download sherpa-onnx multilingual ASR model.

SenseVoice: zh, en, ja, ko, yue (Cantonese) — ~200MB
Source: https://github.com/k2-fsa/sherpa-onnx/releases
"""
import urllib.request
import tarfile
import shutil
import sys
from pathlib import Path

MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2"
)
MODEL_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

def main():
    models_dir = Path(__file__).resolve().parent.parent / "models"
    dest = models_dir / "sherpa-onnx-paraformer"
    tar_path = models_dir / f"{MODEL_NAME}.tar.bz2"

    models_dir.mkdir(exist_ok=True)

    # Download
    print(f"Downloading {MODEL_NAME}...")
    print(f"  URL: {MODEL_URL}")
    print(f"  Size: ~200MB")

    def report(count, block_size, total_size):
        pct = int(count * block_size * 100 / total_size) if total_size > 0 else 0
        mb = count * block_size / (1024 * 1024)
        sys.stdout.write(f"\r  {mb:.0f}MB ({pct}%)")
        sys.stdout.flush()

    urllib.request.urlretrieve(MODEL_URL, tar_path, reporthook=report)
    print("\n  Done.")

    # Extract
    print(f"Extracting to {dest}...")
    if dest.exists():
        shutil.rmtree(dest)

    with tarfile.open(tar_path, "r:bz2") as tar:
        tar.extractall(path=models_dir)

    # Rename to expected path
    extracted = models_dir / MODEL_NAME
    extracted.rename(dest)

    # Cleanup
    tar_path.unlink()

    # Verify
    files = list(dest.glob("*"))
    print(f"Installed {len(files)} files to {dest}:")
    for f in sorted(files):
        size_mb = f.stat().st_size / (1024 * 1024) if f.is_file() else 0
        print(f"  {f.name} ({size_mb:.1f}MB)" if f.is_file() else f"  {f.name}/")

    print("\nASR model ready. Restart backend to use it.")


if __name__ == "__main__":
    main()
