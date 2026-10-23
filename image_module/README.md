# KhabarNazar - Image Analysis Module

Detects whether an image is **real or AI-generated** and explains the decision with **Grad-CAM** and **LIME**.

## Datasets (not in the repo)
| Dataset | Role | Link |
|---|---|---|
| AI vs Real (60k) | Training + test | [Kaggle](https://www.kaggle.com/datasets/tristanzhang32/ai-generated-images-vs-real-images) |
| Tiny-GenImage (35k, 7 generators) | Second training dataset, unseen-generator test | [Hugging Face](https://huggingface.co/datasets/TheKernel01/Tiny-GenImage) |
| Misinfo-dataset (8k, FLUX / Imagen 3 / PixArt / SDXL) | Unseen test (fake-news topics) | [Kaggle](https://www.kaggle.com/datasets/bohdan213/misinfo-dataset) |

## Notebooks
| # | Content |
|---|---|
| 00 | Environment and data check |
| 01 | Preprocessing (same size/format for all images, removes shortcuts) |
| 02 | ResNet18 training on AI vs Real: learning-rate test, baselines, metrics |
| 03 | Tiny-GenImage training, unseen-generator test, Misinfo evaluation |
| 04 | Grad-CAM and LIME explanations |
| 05 | Improving Misinfo: CLIP / DINOv2 features, robust augmentation, ensemble, few-shot adaptation |

## Results
| Model | AI vs Real | Tiny-GenImage | Misinfo* |
|---|---|---|---|
| ResNet18 (Stage 2) | 93.8% | 92.0% | 73.2% |
| **Ensemble (CLIP + DINOv2 + ResNet18), zero-shot** | **94.6%** | **91.5%** | **84.0%** (AUC 0.910) |
| Ensemble (CLIP + DINOv2), few-shot** | 91.1% | 87.3% | **96.7%** (AUC 0.993) |

\* Misinfo scored on the same fixed 80% test split for every model.
\*\* Few-shot = classifier also trained on the other 20% of Misinfo, so Misinfo is **not** unseen for this row.

Other findings: transfer learning beat a CNN trained from scratch (94% vs 79.5%); unseen generators GLIDE (92%) and Wukong (85%) were detected but VQDM was not (19%); CLIP generalised best of the single models.

## Models (`models/`)
`resnet18_final.pth` (ResNet18), `resnet18_robust.pth` (with JPEG/resize/blur augmentation), `clip_vitl14_head*.joblib` and `dinov2_l_head*.joblib` (classifiers on frozen CLIP / DINOv2 features; `_fewshot20` = few-shot version).

## Setup
```
python -m venv venv
venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
jupyter notebook
```

Reference: Pelekh, B. (2025). *AI-Generated Image Detection System for Mitigating Fake News and Misinformation*. Ukrainian Catholic University.
