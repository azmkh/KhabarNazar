# KhabarNazar - Urdu Text Module

Detects whether **Urdu-script** news text is fake or real. Model: **XLM-RoBERTa base** fine-tuned on **Hook and Bait
Urdu**, text cleaned with **Urduhack**, tested on **Bend the Truth** as an outside dataset it never trains on.

## Datasets (not in the repo; the notebook downloads them)
| Dataset | Role | Link |
|---|---|---|
| Hook and Bait Urdu (78,409 headlines; Harris et al., *Scientific Reports* 2025) | Training, validation, in-domain test | [GitHub](https://github.com/Sheetal83/Hook-and-Bait-Urdu) |
| Bend the Truth (900 full articles; Amjad et al., 2020) | Outside test only | [GitHub](https://github.com/MaazAmjad/Datasets-for-Urdu-news) |

Not used: Ax-to-Grind (about 95% of it is already inside Hook and Bait) and the FIRE 2020 test set (labels not public).

## What the notebook does (`notebooks/urdu_fake_news_training.ipynb`)
| Part | Steps |
|---|---|
| A. Setup | install check, GPU check, paths and settings |
| B. Data | download both datasets, load them into one format, length per class |
| C. Cleaning | Urduhack normalization, punctuation removal; remove duplicates, label conflicts and fact-check headlines that state their own verdict (leakage); 80/10/10 split |
| D. Baselines | length-only model (shortcut check), character TF-IDF + Logistic Regression |
| E. XLM-RoBERTa | training, test-set and Bend the Truth evaluation (first tokens and whole article), per-file check, error analysis, saving to `models/text/xlmr/`, test through the backend |
| F. Optional | mBERT / MuRIL comparison, SHAP word importance |

## Results
From `outputs/results.csv` (full run on Colab T4, 54,212 training items, 4 epochs, about 18 minutes of training).

| Model | Hook and Bait test (macro-F1) | Bend the Truth (macro-F1) |
|---|---|---|
| Length only | 0.52 | 0.36 |
| Punctuation only (no words) | 0.79 | |
| Character TF-IDF + Logistic Regression | 0.89 | 0.50 |
| **XLM-RoBERTa base** | **0.94** (accuracy 94.4%) | **0.56** (whole article: 0.49) |

- **In-domain:** XLM-RoBERTa beats the TF-IDF baseline by 5 points and the punctuation-only model by 15.
- **Hardest fakes:** per Hook and Bait file, 95-98% of items are classified correctly, except `Fake_News_After_31190.xlsx`
  (fakes written like normal news): 70%.
- **Outside dataset:** on Bend the Truth (full articles written by journalists) the model is only slightly better than
  chance. It works on headline-style Urdu news like its training data, not yet on long articles in a different style.
- **Training curves:** validation loss is lowest after epoch 2 and rises afterwards while validation F1 keeps improving,
  so the model becomes over-confident; the epoch with the best validation F1 (epoch 4) is kept.

**Punctuation shortcut.** In Hook and Bait, the real headlines from two of the three true-news files almost never end
with a full stop (۔), while about 60% of fakes do, and fakes use more question marks. A model that sees only punctuation
scores 0.79. The notebook therefore removes punctuation before training (`REMOVE_PUNCTUATION = True`); the backend reads
that setting from the saved model, so the app cleans text the same way.

## How the backend uses it
`backend/app/ai/text/predict.py` sends **Urdu-script** text to this model when `models/text/xlmr/` exists
(`transformer_model.py`), using the same cleaning as training (`preprocess.clean_urdu_for_model`). Word highlights come
from removing one word at a time and measuring how the model's output changes. Roman Urdu and English still go to the
TF-IDF model or return "Uncertain" until the Roman Urdu model is trained.

## Model file (on the Releases page, not in the folders)
`models/text/xlmr/` is about 1.1 GB, over GitHub's 100 MB limit for normal files, so git ignores that folder. The trained
model is attached to the GitHub Release **text-model-v1** (repo page -> **Releases**). To put it where the backend
looks for it, run from the repo root:
```
python text_module/scripts/download_model_from_release.py
```
Files: `model.safetensors`, `config.json`, `tokenizer.json`, `tokenizer_config.json`, `khabarnazar_config.json`.
A copy is also in Google Drive (`KhabarNazar_models/xlmr`). Re-create it from scratch by running the notebook.

## Setup (Windows)
```
cd text_module
python -m venv venv
venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128   (use the command pytorch.org gives you)
pip install -r requirements.txt
pip install urduhack --no-deps
```
Then open the notebook in VS Code and pick the `venv` kernel.
