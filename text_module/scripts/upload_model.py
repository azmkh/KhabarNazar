"""Optional: share the trained model with teammates through a PRIVATE Hugging Face repo.

The model (models/text/xlmr, about 1 GB) is too big for GitHub, so it is not pushed.
Run from the repo root after training:
    pip install huggingface_hub
    python text_module/scripts/upload_model.py --repo YOUR_HF_USERNAME/khabarnazar-urdu-xlmr
Needs a Hugging Face account and a WRITE token (huggingface.co -> Settings -> Access Tokens).
"""
import argparse
from pathlib import Path

from huggingface_hub import HfApi, login

REPO_ROOT = Path(__file__).resolve().parents[2]

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True, help="e.g. yourname/khabarnazar-urdu-xlmr")
parser.add_argument("--model-dir", default=str(REPO_ROOT / "models" / "text" / "xlmr"))
args = parser.parse_args()

login()
api = HfApi()
api.create_repo(args.repo, private=True, exist_ok=True)
api.upload_folder(folder_path=args.model_dir, repo_id=args.repo, ignore_patterns=["checkpoint-*", ".gitkeep"])
print(f"Uploaded to https://huggingface.co/{args.repo}")
