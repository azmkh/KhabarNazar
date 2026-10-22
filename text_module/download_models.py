"""Download the XLM-R text models from this repo's GitHub Releases.

The models are ~1 GB each, too big for git, so each one is attached to a
GitHub Release. Run from the repo root (no GitHub login needed):

    python text_module/download_models.py            # all models
    python text_module/download_models.py urdu       # only the Urdu model

Files land where the backend looks for them:
    text_module/urdu/models/xlmr/
    text_module/roman_urdu/models/xlmr/
"""
import sys
import urllib.request
from pathlib import Path

REPO = "azmkh/KhabarNazar"
TEXT_MODULE = Path(__file__).resolve().parent
FILES = ["config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"]
MODELS = {
    # name: (release tag, target folder)
    "urdu": ("urdu-xlmr-v1", TEXT_MODULE / "urdu" / "models" / "xlmr"),
    "roman_urdu": ("roman-urdu-xlmr-v1", TEXT_MODULE / "roman_urdu" / "models" / "xlmr"),
}


def progress(blocks: int, block_size: int, total: int) -> None:
    if total > 0:
        done = min(blocks * block_size, total)
        sys.stdout.write(f"\r    {done / 1e6:8.1f} / {total / 1e6:.1f} MB")
        sys.stdout.flush()


def download(name: str) -> None:
    tag, folder = MODELS[name]
    folder.mkdir(parents=True, exist_ok=True)
    print(f"\n{name}: release {tag} -> {folder}")
    for file in FILES:
        target = folder / file
        if target.is_file() and target.stat().st_size > 0:
            print(f"  {file}: already there, skipped")
            continue
        url = f"https://github.com/{REPO}/releases/download/{tag}/{file}"
        print(f"  {file}")
        try:
            urllib.request.urlretrieve(url, target.with_suffix(target.suffix + ".part"), progress)
        except Exception as error:  # e.g. the release does not exist yet
            print(f"\n  could not download {url}: {error}")
            return
        target.with_suffix(target.suffix + ".part").replace(target)
        print()
    print(f"  done: {name}")


if __name__ == "__main__":
    names = sys.argv[1:] or list(MODELS)
    unknown = [n for n in names if n not in MODELS]
    if unknown:
        sys.exit(f"unknown model(s) {unknown}; choose from {list(MODELS)}")
    for model_name in names:
        download(model_name)
