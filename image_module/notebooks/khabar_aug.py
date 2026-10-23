"""Augmentations used by notebook 05.

They live in a .py file (not inside the notebook) because on Windows the DataLoader
worker processes cannot see classes defined inside a notebook.
"""
import io
import random

from PIL import Image


class RandomRescale:
    """Randomly shrink or enlarge the whole image (simulates images re-sized by websites/apps)."""

    def __init__(self, low=0.5, high=1.5, p=0.5, min_side=224):
        self.low, self.high, self.p, self.min_side = low, high, p, min_side

    def __call__(self, img):
        if random.random() >= self.p:
            return img
        w, h = img.size
        s = max(random.uniform(self.low, self.high), self.min_side / min(w, h))
        method = random.choice([Image.BILINEAR, Image.BICUBIC, Image.LANCZOS])
        return img.resize((max(1, round(w * s)), max(1, round(h * s))), method)


class RandomJPEG:
    """Randomly re-save the image as JPEG at quality 60-95 (simulates WhatsApp/Facebook/blog compression)."""

    def __init__(self, low=60, high=95, p=0.5):
        self.low, self.high, self.p = low, high, p

    def __call__(self, img):
        if random.random() >= self.p:
            return img
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=random.randint(self.low, self.high))
        buf.seek(0)
        return Image.open(buf).convert("RGB")
