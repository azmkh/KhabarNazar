# Roman Urdu fake news detection

The Roman Urdu part of the **KhabarNazar** text module. It classifies a Roman Urdu news item as **real** or **fake**. The model used by the app is `xlm-roberta-large` fine-tuned on the KhabarNazar Roman Urdu dataset, which we built.

**Final result (test set, 826 articles):** XLM-R large **0.842 macro-F1** (84.3% accuracy); combined with a TF-IDF model **0.846** (84.6%). A character n-gram TF-IDF baseline scores 0.816.

## Dataset

8,267 Urdu news items from four public datasets, transliterated to Roman Urdu with Claude (an LLM). The real/fake labels come from the original datasets.

| Source | Style | Real | Fake | Total |
|---|---|---|---|---|
| Hook and Bait Urdu | headlines (median 26 words) | 2,100 | 2,100 | 4,200 |
| Ax-to-Grind Urdu | short items (median 28 words) | 1,238 | 1,237 | 2,475 |
| Bend the Truth | full articles (median 260 words) | 496 | 398 | 894 |
| FIRE 2021 (UrduFake) | full articles (median 204 words) | 448 | 250 | 698 |
| **Total** | | **4,282** | **3,985** | **8,267** |

Columns: `id`, `source_dataset`, `original_text` (Urdu script), `label`, `roman_text`.

**The article text is not in this repository.** The source datasets belong to their authors, so we don't redistribute them. `outputs/split_ids.csv` lists which article ids are in each split, so anyone with the data can rebuild the exact split. Output files in this folder contain ids, labels and probabilities only.

## Split

80/10/10 into train (6,615), validation (826) and test (826), stratified by source and label (`notebooks/01_make_splits.ipynb`). Every result below uses this same split.

Near-duplicate articles are grouped (word-trigram Jaccard ≥ 0.5) and each group stays in one split, so a fake article and the real article it was made from are never split across train and test. 155 groups were found.

**How the fakes in Bend the Truth and FIRE were made.** Comparing each fake article with every real article from the same source:

| Source | Fakes | Near-copy of a real article (overlap ≥ 0.5) | Rewrite of a real story (overlap ≥ 0.2) |
|---|---|---|---|
| Bend the Truth | 398 | 37 (9%) | 293 (74%) |
| FIRE 2021 | 250 | 32 (13%) | 116 (46%) |

So most Bend the Truth fakes are the same real news story rewritten with some facts changed: same topic, same journalistic style, similar length.

## Results (test set, macro-F1)

| Model | Accuracy | All | Ax-to-Grind | Hook and Bait | FIRE | Bend the Truth |
|---|---|---|---|---|---|---|
| TF-IDF (char 2-5 + word 1-2 grams) + LR | 0.816 | 0.816 | 0.801 | 0.883 | 0.620 | 0.658 |
| XLM-R base, mean of 3 runs | 0.827 | 0.826 ± 0.016 | 0.806 | 0.897 | 0.695 | 0.602 |
| MuRIL base, mean of 3 runs | 0.818 | 0.818 ± 0.015 | 0.818 | 0.877 | 0.682 | 0.592 |
| XLM-R + MuRIL + TF-IDF (7 models) | 0.844 | 0.843 | 0.838 | 0.912 | 0.662 | 0.628 |
| **XLM-R large** (used by the app) | **0.843** | **0.842** | 0.825 | 0.914 | **0.741** | 0.589 |
| **XLM-R large + TF-IDF** | **0.846** | **0.846** | 0.825 | **0.921** | 0.707 | 0.612 |

Test articles per source: Ax-to-Grind 247, Hook and Bait 420, FIRE 70, Bend the Truth 89.

### Findings

1. **Run-to-run variation is large.** The same XLM-R base setup scored 0.812 to 0.844 depending only on the random seed (0.826 ± 0.016). Differences of 1-2 points between single runs are not meaningful, so we report means over 3 runs.
2. **XLM-R base and MuRIL are on par with TF-IDF.** A paired bootstrap over the test set (2,000 resamples) found no clear difference between the TF-IDF baseline and any base-size model or ensemble (95% intervals include 0).
3. **XLM-R large is the best single model** (0.842). **XLM-R large + TF-IDF (0.846) is the only model clearly better than TF-IDF**: +0.030 macro-F1, 95% CI +0.004 to +0.057.
4. **MuRIL**, pre-trained on South Asian languages including transliterated text, did not beat XLM-R.
5. **Bend the Truth stays at about 0.6 with every model**, and TF-IDF is best on it. Its fakes are rewritten versions of real stories (see above), so they cannot be told apart by writing style. A TF-IDF model trained without any Bend the Truth articles scores almost the same on them (0.647) as one trained with them (0.658).
6. **Oversampling the article sources and head + tail truncation did not help** (notebook 03: 0.825 overall, Bend the Truth 0.652). Validation gains on the 88-article Bend the Truth validation set did not carry over to the test set.

### Training notes

- One of four MuRIL runs (seed 13) and the first XLM-R large run (seed 42, learning rate 1e-5) **collapsed**: they predicted "Real" for every article (validation accuracy 0.518). They were replaced by new seeds; XLM-R large trained normally with seed 21 and learning rate 8e-6.
- XLM-R large was trained once (38 minutes on an RTX A4000), so it has no ± value.

Numbers: `outputs/results_table.csv` (Colab), `outputs/results_table_run2.csv` (notebook 03), `outputs/results_04.csv` (notebook 04), `outputs/results_05_xlmr_large.csv` (notebook 05).

## Notebooks

| Notebook | What it does | Where it ran |
|---|---|---|
| `01_make_splits.ipynb` | Fixed train/validation/test split with near-duplicate grouping | any computer |
| `02_train_xlmr.ipynb` | First XLM-R base run and TF-IDF baseline (0.833) | Google Colab, T4 |
| `03_train_xlmr_gpu.ipynb` | Experiment: oversampling + head/tail truncation (no improvement) | RTX A4000 |
| `04_seeds_muril_ensemble.ipynb` | TF-IDF, XLM-R × 3 seeds, MuRIL × 3 seeds, ensembles, bootstrap test | RTX A4000 |
| `05_final_model.ipynb` | Final model: XLM-R large + TF-IDF, saved for the app | RTX A4000 |

## Model used by the app

The backend sends Roman Urdu (Latin-letter) input to XLM-R large (`backend/app/ai/text/xlmr.py`), reading it from `roman_urdu/models/xlmr/`. Inputs are cut at 512 tokens, as in training.

The model (about 1.1 GB, stored in half precision so it fits GitHub's 2 GB file limit) is attached to the GitHub Release **`roman-urdu-xlmr-v1`**. To download it into the right folder, run from the repo root:

```
python text_module/download_models.py roman_urdu
```

Labels: `0 = Real`, `1 = Fake`.

## How to reproduce

1. Put `khabarnazar_roman_urdu_dataset.csv` in `data/` and run `notebooks/01_make_splits.ipynb` (or use `outputs/split_ids.csv` directly).
2. Set the paths in the first cell of a notebook to your folders. Notebooks 03-05 were run on a Windows PC with the data on `E:\KhabarNazar_text\`.
3. Run all cells. Notebooks 04 and 05 save each run's predictions, so a run interrupted by a restart or power cut continues where it stopped.

Settings shared by all transformer runs: max length 512 tokens, effective batch 16, up to 5 epochs, early stopping on validation macro-F1, bf16 mixed precision. Base models: learning rate 2e-5. XLM-R large: learning rate 8e-6, batch 4 × 4 gradient accumulation, gradient checkpointing.

### Setting up a GPU computer

1. Check that the NVIDIA driver works: `nvidia-smi` should list the GPU and a "CUDA Version".
2. Create an environment (Python 3.10 to 3.12):
   ```bash
   cd text_module/roman_urdu
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   ```
3. Install PyTorch **with CUDA** first, using the command from pytorch.org (Get Started), for example:
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu128
   ```
   Then: `pip install -r requirements.txt jupyter`
4. Check: `python -c "import torch; print(torch.cuda.is_available())"` should print `True`.

The first run downloads the pre-trained models from Hugging Face (`xlm-roberta-base` 1.1 GB, `xlm-roberta-large` 2.2 GB, `google/muril-base-cased` 0.95 GB). On networks where these downloads stall, set `HF_HUB_DISABLE_XET=1` (the notebooks already do).

## Limitations

- **Style, not facts.** The model learns how fake news is *written*. It cannot check whether a claim is true, which is why rewritten fakes (Bend the Truth) remain hard.
- **Transliteration by an LLM.** Roman Urdu was generated by Claude, not written by people, and real users spell Roman Urdu inconsistently. _Quality check: not done yet (planned: about 100 random rows read by a native speaker)._
- **Length bias in FIRE.** Real FIRE articles are longer than fake ones (median 248 vs 167 words). Word count alone reaches 0.59 macro-F1 on FIRE, so part of any FIRE score may come from length.
- **Small per-source test sets.** Bend the Truth (89) and FIRE (70) scores have about ±10 points of uncertainty.
- **Truncation.** Articles longer than 512 tokens are cut (about 5% overall, mostly Bend the Truth and FIRE).

## Folder structure

```
roman_urdu/
├── README.md
├── requirements.txt
├── data/
│   └── README.md            # data files are kept out of git
├── notebooks/
│   ├── 01_make_splits.ipynb
│   ├── 02_train_xlmr.ipynb
│   ├── 03_train_xlmr_gpu.ipynb
│   ├── 04_seeds_muril_ensemble.ipynb
│   └── 05_final_model.ipynb
├── models/xlmr/             # downloaded from the release, not in git
└── outputs/
    ├── split_ids.csv, split_report.json
    ├── results_table.csv, metrics.json, test_predictions.csv, training_log.csv    (notebook 02)
    ├── results_table_run2.csv                                                     (notebook 03)
    ├── results_04.csv                                                             (notebook 04)
    ├── results_05_xlmr_large.csv                                                  (notebook 05)
    └── *.png                                                                      (plots)
```

## Source datasets

- Bend the Truth: Amjad et al., "Bend the Truth: Benchmark dataset for fake news detection in Urdu language and its evaluation", *Journal of Intelligent & Fuzzy Systems*, 2020.
- FIRE 2021 UrduFake shared task: Amjad et al., "Overview of the shared task on fake news detection in Urdu at FIRE 2021".
- Ax-to-Grind Urdu: Harris et al., "Ax-to-Grind Urdu: Benchmark dataset for Urdu fake news detection", 2023.
- Hook and Bait Urdu: Harris et al., "Hook and Bait Urdu: A large-scale benchmark dataset for Urdu fake news detection".

_Check these citations against the papers before submitting._

## Team

Waniya Farooq Khan, Muhammad Azeem Khan, Muhammad Shabeeh Abbas Sheikh. Supervisor: Sir Ishaq Raza. FAST-NUCES Lahore.
