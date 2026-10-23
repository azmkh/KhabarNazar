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
import re
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


def download_file(url: str, partial: Path) -> None:
    """Download in large chunks, resuming a valid HTTP range when available."""
    offset = partial.stat().st_size if partial.is_file() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=90) as response:
        status = getattr(response, "status", 200)
        content_range = response.headers.get("Content-Range", "")
        if offset and status == 206:
            match = re.match(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range)
            if not match or int(match.group(1)) != offset:
                raise ValueError("Server returned an invalid Content-Range for the partial model file")
            expected_response_bytes = int(match.group(2)) - offset + 1
            total_bytes = None if match.group(3) == "*" else int(match.group(3))
            mode = "ab"
        else:
            # The server ignored Range (or the file was new): start this partial file over.
            offset = 0
            expected_response_bytes = response.headers.get("Content-Length")
            expected_response_bytes = int(expected_response_bytes) if expected_response_bytes else None
            total_bytes = expected_response_bytes
            mode = "wb"

        received = 0
        next_report = 10 * 1024 * 1024
        with partial.open(mode) as output:
            while block := response.read(1024 * 1024):
                output.write(block)
                received += len(block)
                if received >= next_report:
                    done = offset + received
                    size = f" / {total_bytes / 1e6:.1f} MB" if total_bytes else ""
                    print(f"    {done / 1e6:.1f} MB{size}", flush=True)
                    next_report += 10 * 1024 * 1024

        if expected_response_bytes is not None and received != expected_response_bytes:
            raise IOError(f"Incomplete download: received {received} of {expected_response_bytes} bytes")
        if total_bytes is not None and partial.stat().st_size != total_bytes:
            raise IOError(f"Incomplete download: file has {partial.stat().st_size} of {total_bytes} bytes")


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
            download_file(url, target.with_suffix(target.suffix + ".part"))
        except Exception as error:  # e.g. the release does not exist yet
            print(f"\n  could not download {url}: {error}")
            raise SystemExit(1) from error
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
