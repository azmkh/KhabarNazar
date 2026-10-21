"""Optional: download the trained model into models/text/xlmr (for teammates who did not train it).

Run from the repo root:
    pip install huggingface_hub
    python text_module/scripts/download_model.py --repo OWNER_HF_USERNAME/khabarnazar-urdu-xlmr
The repo is private: you need a READ token from an account that has access to it.
"""
import argparse
from pathlib import Path

from huggingface_hub import login, snapshot_download

REPO_ROOT = Path(__file__).resolve().parents[2]

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--out", default=str(REPO_ROOT / "models" / "text" / "xlmr"))
args = parser.parse_args()

login()
print("Model downloaded to", snapshot_download(repo_id=args.repo, local_dir=args.out))
