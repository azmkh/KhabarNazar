"""AI-generated vs real image detector from image_module/ (notebook 05, zero-shot ensemble).

The ensemble averages P(real) from three members, exactly as notebook 05 scored it:
  - CLIP ViT-L/14 image embedding  -> clip_vitl14_head.joblib (Normalizer, StandardScaler, LogisticRegression)
  - DINOv2-L pooled embedding      -> dinov2_l_head.joblib
  - ResNet18 with robust augmentation (resnet18_robust.pth)
The few-shot heads (*_fewshot20.joblib) were partly trained on the Misinfo test domain, so they are not used.

Preprocessing matches the notebooks: RGB, shorter side scaled to 512 (never below 224, notebook 01),
then a 224x224 centre crop and per-backbone normalization (notebook 05, "crop" mode).
Only that centre crop is analysed. The result says whether the pixels look AI-generated; it says
nothing about whether a news claim is true.

PyTorch/transformers are imported lazily, so the API still starts without them and reports the
detector as unavailable. The CLIP and DINOv2 backbones are downloaded from Hugging Face on first load.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[4] / "image_module" / "models"
MODEL_VERSION = "img-ens-clip-dino-r18"  # stored in VARCHAR(50) columns

# Label mapping, in one place. ImageFolder sorted the class folders, so index 0 = fake, 1 = real.
CLASSES = ("fake", "real")
REAL_INDEX = 1
THRESHOLD = 0.5  # notebook 05 scored every model at a fixed 0.5 on P(real)
LABEL_AI_GENERATED = "Likely AI-generated"
LABEL_REAL = "Likely real photo"

SHORT_SIDE, MIN_SIDE, CROP = 512, 224, 224
IMAGENET_MEAN, IMAGENET_STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
CLIP_MEAN, CLIP_STD = (0.4815, 0.4578, 0.4082), (0.2686, 0.2613, 0.2758)
CLIP_HF, DINO_HF = "openai/clip-vit-large-patch14", "facebook/dinov2-large"
REQUIRED_FILES = ("clip_vitl14_head.joblib", "dinov2_l_head.joblib", "resnet18_robust.pth")


def model_dir() -> Path:
    return Path(os.environ.get("KHABARNAZAR_IMAGE_MODEL_DIR", str(DEFAULT_MODEL_DIR))).expanduser()


def standardise(img):
    """Notebook 01: RGB, shorter side 512 (or kept, but at least 224), bicubic."""
    img = img.convert("RGB")
    width, height = img.size
    short = min(width, height)
    target = SHORT_SIDE if short > SHORT_SIDE else max(short, MIN_SIDE)
    if target != short:
        scale = target / short
        from PIL import Image

        img = img.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.BICUBIC)
    return img


def crop_box(size: tuple[int, int]) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of torchvision's CenterCrop(224) on an image of this size."""
    width, height = size
    left, top = int(round((width - CROP) / 2.0)), int(round((height - CROP) / 2.0))
    return left, top, left + CROP, top + CROP


class AIImageDetector:
    def __init__(self, directory: Path):
        import joblib
        import torch
        from torch import nn
        from torchvision import models, transforms
        from transformers import AutoModel, CLIPVisionModelWithProjection

        self.torch = torch
        self.clip_head = joblib.load(directory / "clip_vitl14_head.joblib")
        self.dino_head = joblib.load(directory / "dinov2_l_head.joblib")
        for head in (self.clip_head, self.dino_head):
            if list(head.classes_) != [0, 1]:
                raise ValueError(f"unexpected classifier classes {head.classes_}")

        resnet = models.resnet18(weights=None)
        resnet.fc = nn.Linear(resnet.fc.in_features, len(CLASSES))
        resnet.load_state_dict(torch.load(directory / "resnet18_robust.pth", map_location="cpu", weights_only=True))
        self.resnet = resnet.eval()
        from transformers.utils import logging as hf_logging

        # CLIP's checkpoint also holds its text half, which the vision model does not use;
        # transformers would print every unused text weight as "UNEXPECTED".
        verbosity = hf_logging.get_verbosity()
        hf_logging.set_verbosity_error()
        try:
            self.clip = CLIPVisionModelWithProjection.from_pretrained(CLIP_HF).eval()
            self.dino = AutoModel.from_pretrained(DINO_HF).eval()
        finally:
            hf_logging.set_verbosity(verbosity)

        def pipeline(mean, std):
            return transforms.Compose([transforms.CenterCrop(CROP), transforms.ToTensor(), transforms.Normalize(mean, std)])

        self.imagenet_tf = pipeline(IMAGENET_MEAN, IMAGENET_STD)
        self.clip_tf = pipeline(CLIP_MEAN, CLIP_STD)

    def analyse(self, img) -> dict:
        """P(real) per member and for the ensemble, plus a Grad-CAM map from the ResNet18 member."""
        torch = self.torch
        img = standardise(img)
        imagenet_x = self.imagenet_tf(img).unsqueeze(0)
        with torch.no_grad():
            clip_features = self.clip(pixel_values=self.clip_tf(img).unsqueeze(0)).image_embeds.numpy()
            dino_features = self.dino(pixel_values=imagenet_x).pooler_output.numpy()
        p_clip = float(self.clip_head.predict_proba(clip_features)[0, REAL_INDEX])
        p_dino = float(self.dino_head.predict_proba(dino_features)[0, REAL_INDEX])
        p_resnet, cam = self._resnet_with_gradcam(imagenet_x)
        p_real = (p_clip + p_dino + p_resnet) / 3
        return {
            "p_real": p_real,
            "members": {"clip_vitl14": p_clip, "dinov2_l": p_dino, "resnet18_robust": p_resnet},
            "attribution_map": self._place_in_image(cam, img.size),
        }

    def _resnet_with_gradcam(self, x):
        """Notebook 04's Grad-CAM on the last ResNet18 block, for the class the ResNet member predicts."""
        torch = self.torch
        store: dict = {}

        def hook(_module, _inputs, output):
            store["acts"] = output
            output.register_hook(lambda grad: store.__setitem__("grads", grad))

        handle = self.resnet.layer4[-1].register_forward_hook(hook)
        try:
            x = x.clone().requires_grad_(True)
            with torch.enable_grad():
                logits = self.resnet(x)
                p_real = float(torch.softmax(logits, 1)[0, REAL_INDEX])
                logits[0, int(logits.argmax(1))].backward()
            weights = store["grads"].mean(dim=(2, 3), keepdim=True)
            cam = torch.relu((weights * store["acts"]).sum(1))[0].detach()
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
        finally:
            handle.remove()
            self.resnet.zero_grad(set_to_none=True)
        return p_real, cam.numpy()

    @staticmethod
    def _place_in_image(cam, size: tuple[int, int]):
        """Put the 224x224 crop's map back at its place in the (standardised) image; zero elsewhere."""
        import cv2
        import numpy as np

        width, height = size
        left, top, right, bottom = crop_box(size)
        full = np.zeros((height, width), dtype=np.float32)
        crop_map = cv2.resize(cam.astype(np.float32), (CROP, CROP), interpolation=cv2.INTER_LINEAR)
        # A crop can stick out of an image whose side is exactly 224 after rounding; clip both sides.
        src_left, src_top = max(0, -left), max(0, -top)
        left, top, right, bottom = max(0, left), max(0, top), min(width, right), min(height, bottom)
        full[top:bottom, left:right] = crop_map[src_top:src_top + bottom - top, src_left:src_left + right - left]
        return full if float(full.max()) > float(full.min()) else None


_lock = threading.Lock()
_cache: dict[str, AIImageDetector] = {}


def load_detector() -> tuple[Optional[AIImageDetector], Optional[str]]:
    """Return (detector, None) or (None, reason it is unavailable). Loads once per process."""
    directory = model_dir()
    missing = [name for name in REQUIRED_FILES if not (directory / name).is_file()]
    if missing:
        return None, "The AI-generated image detector is not installed (model files are missing)."
    key = str(directory.resolve())
    with _lock:
        if key not in _cache:
            try:
                _cache[key] = AIImageDetector(directory)
            except ImportError:
                return None, "The AI-generated image detector needs torch, torchvision and transformers."
            except Exception:
                logger.exception("Could not load the AI-generated image detector from %s", directory)
                return None, "The AI-generated image detector could not be loaded. Check the backend log."
        return _cache[key], None


def label_for(p_real: float) -> str:
    return LABEL_REAL if p_real >= THRESHOLD else LABEL_AI_GENERATED
