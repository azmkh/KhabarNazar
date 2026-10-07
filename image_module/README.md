# KhabarNazar - Image Analysis Module

Detects whether an image is **real or AI-generated** and explains the decision with **Grad-CAM** and **LIME**.
Model: ResNet18 (ImageNet-pretrained), fully fine-tuned, trained in two stages on two datasets and tested on a third, unseen dataset.

## Datasets (not included in the repo - download separately)
| Dataset | Role | Images | Source |
|---|---|---|---|
| AI vs Real (tristanzhang32) | Stage-1 training + test | 48k train / 12k test | https://www.kaggle.com/datasets/tristanzhang32/ai-generated-images-vs-real-images |
| Tiny-GenImage | Stage-2 training, unseen-generator test (7 generators) | 28k train / 7k val | https://huggingface.co/datasets/TheKernel01/Tiny-GenImage |
| Misinfo-dataset | Unseen test only (FLUX, Imagen 3, PixArt, SDXL; fake-news topics) | 8k | https://www.kaggle.com/datasets/bohdan213/misinfo-dataset |

## Notebooks (run in order)
| Notebook | Content |
|---|---|
| `00_data_check.ipynb` | GPU check, dataset counts, sample images |
| `01_preprocess.ipynb` | Same resizing (shorter side 512) and JPEG format for every image, removing size/format shortcuts |
| `02_train_ai_vs_real.ipynb` | Learning-rate experiment, baselines (simple CNN, ResNet18 head-only, ResNet18 full), final Stage-1 model, test metrics, ROC/PR, mistakes, t-SNE |
| `03_tiny_genimage_and_unseen.ipynb` | Cross-dataset test, unseen-generator experiment, Stage-2 joint training, final comparison, Misinfo per-generator results |
| `04_explainability.ipynb` | Grad-CAM and LIME on all test sets, and on any single image |

## Results
**Stage 1 baselines (AI vs Real test set, 12,000 images)**

| Model | Accuracy | F1 | ROC AUC |
|---|---|---|---|
| Simple CNN (from scratch) | 79.5% | 0.795 | 0.874 |
| ResNet18, final layer only | 81.6% | 0.816 | 0.900 |
| ResNet18, all layers (lr 1e-4) | **93.95%** | **0.940** | **0.985** |

**Effect of the second dataset**

| Model | AI vs Real | Tiny-GenImage | Misinfo (unseen) |
|---|---|---|---|
| Stage 1: AI vs Real only | 93.95% | 56.5% | 74.8% (AUC 0.853) |
| Stage 2: AI vs Real + Tiny-GenImage | 93.8% | **92.0%** | 73.0% (AUC 0.862) |

**Unseen-generator experiment** (fine-tuned on ADM, BigGAN, Midjourney, SD 1.5 only): unseen GLIDE detected 92%, Wukong 85%, VQDM 19%.

**Misinfo, final model:** AI images detected - FLUX 99%, PixArt 99%, SDXL 88%, Imagen 3 66%; about 58% of real photos correctly accepted.

**Limitations:** the model over-flags unfamiliar real photos, struggles with generators unlike its training data (VQDM, Imagen 3), and has not yet been trained to handle JPEG-compressed web/social-media images.

## Models (`models/`)
- `resnet18_ai_vs_real.pth` - Stage-1 model
- `resnet18_final.pth` - **final model** (Stage 2)

## Setup
```
python -m venv venv
venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
python -m ipykernel install --user --name khabarnazar --display-name "Python 3 (KhabarNazar)"
jupyter notebook
```

## Reference
Pelekh, B. (2025). *AI-Generated Image Detection System for Mitigating Fake News and Misinformation*. Ukrainian Catholic University.
