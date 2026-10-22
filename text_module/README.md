# KhabarNazar - Text Analysis Module (Urdu + Roman Urdu)

Classifies Urdu-script and Roman Urdu news text as **real or fake**.

## Datasets (not in the repo)
| Dataset | Size | Role | Link |
|---|---|---|---|
| Hook and Bait Urdu | 78,409 items (42,179 real / 36,230 fake) | Main training set | [GitHub](https://github.com/Sheetal83/Hook-and-Bait-Urdu) |
| Ax-to-Grind Urdu | 10,083 items (5,030 real / 5,053 fake) | Second training set, cross-dataset test | [GitHub](https://github.com/Sheetal83/Ax-to-Grind-Urdu-Dataset) (use `Combined .csv`; `Fake News.csv` has its Urdu saved as `????`) |
| UrduFake @ FIRE 2021 | 1,300 train / 300 test | Benchmark (best published macro-F1 0.679) | [GitHub](https://github.com/MaazAmjad/Urdu-Fake-news-detection-FIRE2021) |
| **KhabarNazar Roman Urdu** (ours) | 8,267 items (4,282 real / 3,985 fake) | Roman Urdu training + test | built from the four Urdu datasets above, transliterated |

Bend the Truth is not used on its own: it is already part of the FIRE 2021 training set.

## Folder layout
```
text_module/
   README.md, requirements.txt
   urdu/                       Urdu-script model
      notebooks/urdu_fake_news_xlmr.ipynb
      outputs/                 results.csv, length plot, confusion matrices
      models/
         xlmr/                 XLM-R (E1), ~1 GB - not in git, download link below
         tfidf_long_articles.joblib   long-article model (in git)
   roman_urdu/                 Roman Urdu model
      notebooks/
      outputs/
      models/xlmr/             XLM-R, ~1 GB - not in git, download link below
```
The backend loads the models from these folders (`backend/app/ai/text/`).

# Urdu script (`urdu/`)

## Data cleaning findings
- **Hook and Bait contains Ax-to-Grind:** 8,424 Ax-to-Grind articles reappear in Hook and Bait (sometimes lightly edited). Removed from Hook and Bait so Ax-to-Grind stays independent.
- **Ax-to-Grind has ~9% internal duplicates** (9,201 unique of 10,081).
- **Both contain FIRE 2021 training articles** (~320 each). Removed.
- Matching uses a letters-only key (ignores spaces, digits, punctuation), so near-copies are caught.

## Results (macro-F1)
| Model | Trained on | Hook and Bait test | Ax-to-Grind test | FIRE 2021 test |
|---|---|---|---|---|
| Length-only baseline | each dataset | 0.585 | 0.468 | 0.566 |
| TF-IDF + LR | Hook and Bait | 0.957 | 0.620 | 0.501 |
| TF-IDF + LR | Ax-to-Grind | 0.637 | 0.894 | 0.473 |
| TF-IDF + LR | FIRE 2021 | 0.435 | 0.532 | **0.668** |
| XLM-R base (E1) | Hook and Bait | **0.974** | 0.650 | 0.304 |
| XLM-R base (E2) | Ax-to-Grind | 0.688 | **0.916** | 0.314 |
| XLM-R (E3) | Hook and Bait -> FIRE | 0.956 | 0.624 | 0.504 |
| XLM-R (E4) | FIRE only | 0.570 | 0.541 | 0.506 |
| *Best published (2021)* | | | | *0.679* |

## Findings
1. **XLM-R is best inside a dataset** (0.974 Hook and Bait, 0.916 Ax-to-Grind), but only slightly better than TF-IDF (0.957, 0.894).
2. **No model transfers well between datasets** (0.3-0.7 on unseen datasets): each dataset has its own sources and writing style.
3. **On FIRE 2021 (long articles, 1.3k training items) TF-IDF beats XLM-R** (0.668 vs at most 0.506), in line with the 2021 shared task, where a linear model also won.
4. **Ax-to-Grind's length gap is not a real shortcut:** fake items average 3.3x more words, but a length-only model scores 0.47 (chance), and XLM-R drops only 5 points (0.916 -> 0.869) on a length-matched test subset.
5. **Fact-check wording in Hook and Bait** (e.g. جھوٹ, گمراہ کن, وائرل) appears in 18.7% of fake items vs 2.9% of real ones, but XLM-R still scores 0.971 with those words deleted, so it does not rely on them.

## Models used by the app (backend)
| Input | Model | Location | Macro-F1 |
|---|---|---|---|
| Urdu script, up to 150 words | **XLM-R base (E1)**, trained on Hook and Bait | `urdu/models/xlmr/` | 0.974 (Hook and Bait test) |
| Urdu script, over 150 words | TF-IDF + Logistic Regression, trained on FIRE 2021 | `urdu/models/tfidf_long_articles.joblib` | 0.639 (FIRE 2021 test) |
| Roman Urdu | XLM-R base, trained on the KhabarNazar Roman Urdu dataset | `roman_urdu/models/xlmr/` | see below |

Long Urdu articles use TF-IDF because every XLM-R model scored 0.30-0.51 on FIRE 2021, while TF-IDF scored 0.64-0.67 (the published best is 0.679). E1 given only an article's first 40 words scored 0.436.

**Download the XLM-R folders** from: *(add the Google Drive / Hugging Face link here)* and place them in `urdu/models/xlmr/` and `roman_urdu/models/xlmr/`.

# Roman Urdu (`roman_urdu/`)
*(to be added: Roman Urdu notebooks, results and model details)*

## Setup
```
python -m venv venv
venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
jupyter notebook
```
Put the datasets in `urdu/data/raw/` as described at the top of the Urdu notebook.
