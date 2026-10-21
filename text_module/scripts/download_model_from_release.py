"""Download the trained Urdu XLM-RoBERTa model from the repo's GitHub Release into models/text/xlmr.

The model (about 1.1 GB) is too big for normal git, so it is attached to a GitHub Release instead.
Run from the repo root (no GitHub login needed, the repo is public):
    python text_module/scripts/download_model_from_release.py
Optional: --tag text-model-v2 for a newer release, --out some/other/folder.
"""
import argparse
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO = "azmkh/KhabarNazar"
FILES = ["model.safetensors", "config.json", "tokenizer.json", "tokenizer_config.json", "khabarnazar_config.json"]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tag", default="text-model-v1", help="release tag the model files are attached to")
parser.add_argument("--out", default=str(REPO_ROOT / "models" / "text" / "xlmr"))
parser.add_argument("--base-url", default=f"https://github.com/{REPO}/releases/download")
args = parser.parse_args()

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)


def progress(blocks: int, block_size: int, total: int) -> None:
    if total > 0:
        done = min(blocks * block_size, total)
        sys.stdout.write(f"\r  {done / 1e6:8.1f} / {total / 1e6:.1f} MB")
        sys.stdout.flush()


for name in FILES:
    target = out / name
    if target.exists() and target.stat().st_size > 0:
        print(f"{name}: already downloaded, skipping")
        continue
    url = f"{args.base_url}/{args.tag}/{name}"
    print(f"{name}: downloading {url}")
    partial = target.with_suffix(target.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, partial, reporthook=progress)
    except Exception as error:
        partial.unlink(missing_ok=True)
        sys.exit(f"\nFailed to download {name}: {error}\n"
                 f"Check that the release '{args.tag}' exists at https://github.com/{REPO}/releases "
                 f"and has {name} attached.")
    partial.replace(target)
    print()

print(f"Model ready in {out}")
