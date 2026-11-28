"""Build the image-module test assets in images/ and write images/manifest.json.

    python tests/image_cases/make_images.py      (run from PowerShell: headless Edge renders the text)

Nothing is downloaded and no real user upload is used. Text images are rendered by headless Microsoft
Edge, which shapes Urdu correctly. The Pillow build here has no raqm and arabic_reshaper is not installed,
so Pillow alone cannot join Urdu letters. Urdu uses Noto Nastaliq Urdu from the app's own
node_modules/@expo-google-fonts, embedded as a data URL; Latin text uses Segoe UI. Photo-like images are
synthetic (numpy + Pillow: gradients, noise, shapes) and are labelled as such. The repo's only image
fixture, backend/tests/fixtures/urdu_headline.png, is used as is for TC-IMG-06.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
OUT = HERE / "images"
FRONTEND = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "full_pass"))
from ui_pass import Browser  # noqa: E402

FONT = FRONTEND / "node_modules" / "@expo-google-fonts" / "noto-nastaliq-urdu" / "400Regular" / "NotoNastaliqUrdu_400Regular.ttf"
FONT_B64 = base64.b64encode(FONT.read_bytes()).decode()
CSS = f"""@font-face {{ font-family: 'NastaliqTest'; src: url(data:font/ttf;base64,{FONT_B64}) format('truetype'); }}
html, body {{ margin: 0; padding: 0; }} .ur {{ font-family: 'NastaliqTest'; direction: rtl; }} .la {{ font-family: 'Segoe UI', Arial, sans-serif; }}"""
rng = np.random.default_rng(20261128)
manifest: list[dict] = []


def add(case, file, how, **extra):
    p = OUT / file
    manifest.append({"case": case, "file": file, "how_made": how, "bytes": p.stat().st_size,
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), **extra})


class Renderer(Browser):
    def render(self, html: str, width: int, height: int) -> Image.Image:
        self.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
        self.send("Page.navigate", url="about:blank")
        self.pump(0.3)
        doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html}</body></html>"
        self.js(f"document.open(); document.write({json.dumps(doc)}); document.close(); 1")
        self.js("document.fonts.ready.then(() => 1)")
        self.pump(0.8)
        data = self.send("Page.captureScreenshot", format="png", clip={"x": 0, "y": 0, "width": width, "height": height, "scale": 1})["data"]
        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def text_block(text, cls, size, color="#000", bg="#fff", w=1200, h=600, extra=""):
    return (f"<div style='width:{w}px;height:{h}px;background:{bg};display:flex;align-items:center;justify-content:center;{extra}'>"
            f"<div class='{cls}' style='font-size:{size}px;color:{color};line-height:1.9;max-width:{w - 120}px;text-align:center'>{text}</div></div>")


# ─── synthetic photo-like images ──────────────────────────────────────────────

def smooth_noise(h, w, scale, amp):
    small = rng.normal(0, 1, (max(2, h // scale), max(2, w // scale)))
    return np.asarray(Image.fromarray(small.astype(np.float32)).resize((w, h), Image.BICUBIC)) * amp


def landscape(w=1024, h=768):
    y = np.linspace(0, 1, h)[:, None]
    sky = np.stack([120 + 80 * y, 170 + 60 * y, 235 - 20 * y], -1) * np.ones((h, w, 3))
    img = sky.copy()
    yy, xx = np.mgrid[0:h, 0:w]
    sun = np.exp(-(((xx - w * 0.72) ** 2 + (yy - h * 0.22) ** 2) / (2 * (h * 0.05) ** 2)))
    img += sun[..., None] * np.array([120, 90, 20])
    for k, (base, col) in enumerate([(0.55, (90, 120, 80)), (0.65, (60, 110, 50)), (0.78, (40, 90, 35))]):
        ridge = h * base + 40 * np.sin(xx[0] / (90 + 40 * k) + k) + smooth_noise(1, w, 16, 25)[0]
        mask = yy > ridge[None, :]
        tex = smooth_noise(h, w, 6, 18) + rng.normal(0, 9, (h, w))
        img[mask] = (np.array(col) + tex[..., None])[mask]
    img += rng.normal(0, 4, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))


def ai_look(w=1024, h=1024):
    yy, xx = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    img = np.stack([200 + 50 * xx, 140 + 80 * yy, 230 - 60 * xx * yy], -1)
    for _ in range(14):
        cx, cy, r = rng.random(), rng.random(), 0.04 + 0.12 * rng.random()
        glow = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r ** 2)))
        img += glow[..., None] * rng.uniform(40, 110, 3)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))


def street(w=1024, h=768):
    img = Image.fromarray(np.clip(np.stack([np.full((h, w), 150)] * 3, -1) + rng.normal(0, 6, (h, w, 3)), 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    x = 0
    while x < w:
        bw, bh = int(rng.integers(90, 200)), int(rng.integers(250, 600))
        col = tuple(int(c) for c in rng.integers(80, 200, 3))
        d.rectangle([x, h - bh, x + bw, h], fill=col)
        for wy in range(h - bh + 20, h - 40, 40):
            for wx in range(x + 12, x + bw - 20, 30):
                d.rectangle([wx, wy, wx + 14, wy + 22], fill=(230, 220, 150) if rng.random() < 0.4 else (40, 50, 60))
        x += bw + int(rng.integers(0, 12))
    arr = np.asarray(img).astype(float) + rng.normal(0, 7, (h, w, 3))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))


def texture(w=1024, h=768):
    n = sum(smooth_noise(h, w, s, a) for s, a in [(64, 50), (16, 25), (4, 12)]) + rng.normal(0, 8, (h, w))
    base = np.array([130, 115, 95])
    return Image.fromarray(np.clip(base + n[..., None] * np.array([1.0, 0.9, 0.8]), 0, 255).astype(np.uint8))


def portrait(w=768, h=1024):
    bg = np.ones((h, w, 3)) * np.array([70, 85, 100]) + smooth_noise(h, w, 32, 20)[..., None]
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(img)
    d.ellipse([w * 0.3, h * 0.18, w * 0.7, h * 0.62], fill=(214, 170, 140))
    d.rectangle([w * 0.2, h * 0.62, w * 0.8, h], fill=(40, 60, 120))
    for ex in (0.42, 0.58):
        d.ellipse([w * ex - 18, h * 0.36, w * ex + 18, h * 0.39], fill=(50, 40, 35))
    d.arc([w * 0.42, h * 0.44, w * 0.58, h * 0.54], 20, 160, fill=(150, 70, 70), width=6)
    arr = np.asarray(img).astype(float) + rng.normal(0, 5, (h, w, 3))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))


def jpeg_bytes(img, q=90):
    b = io.BytesIO(); img.save(b, "JPEG", quality=q); return b.getvalue()


def data_url(img):
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes(img, 92)).decode()


TXT = {
    "02": "حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔",
    "07": "Hukoomat ne elan kiya hai ke mulk bhar mein saat din ke liye internet service band kar di jayegi.",
    "08": "The government has announced free textbooks for all public schools from 1 November.",
    "09": "حکومت نے petrol کی قیمت میں کمی کا اعلان کیا ہے",
    "10": ["شہر میں آج صبح سے موسلادھار بارش جاری ہے۔", "کئی سڑکوں پر پانی جمع ہونے سے ٹریفک متاثر ہوا۔",
           "انتظامیہ نے شہریوں کو گھروں میں رہنے کی ہدایت کی ہے۔", "محکمہ موسمیات کے مطابق بارش کل تک جاری رہے گی۔"],
    "12": "سیلاب سے متاثرہ علاقوں میں امدادی کارروائیاں جاری ہیں",
    "13": "وفاقی حکومت نے پیٹرول کی قیمت میں دس روپے فی لیٹر اضافہ کر دیا",
    "15": ["Jab teacher kahe kal test nahi hoga", "aur phir agle din surprise test ho jaye"],
}


def controls():
    """Control images: the TC-IMG-02 and TC-IMG-10 text in Segoe UI (Naskh-style Arabic script), to tell an
    OCR limit on Nastaliq apart from a bad render. Appended to the existing manifest."""
    data = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    manifest.extend(i for i in data["images"] if not i["file"].startswith("ctl_"))
    r = Renderer(port=9372)
    try:
        r.render(text_block(TXT["02"], "la", 46, extra="direction:rtl"), 1200, 600).save(OUT / "ctl02_urdu_segoe.png")
        add("control", "ctl02_urdu_segoe.png", "CONTROL: TC-IMG-02 text rendered in Segoe UI (Naskh-style), black on white (1200×600, headless Edge)", text=TXT["02"])
        para = "".join(f"<div>{line}</div>" for line in TXT["10"])
        r.render(f"<div style='width:1200px;height:600px;background:#fff;display:flex;align-items:center;justify-content:center'>"
                 f"<div class='la' style='direction:rtl;font-size:40px;line-height:1.75;text-align:right;width:1040px'>{para}</div></div>", 1200, 600).save(OUT / "ctl10_paragraph_segoe.png")
        add("control", "ctl10_paragraph_segoe.png", "CONTROL: TC-IMG-10 paragraph rendered in Segoe UI (Naskh-style), right-aligned (1200×600, headless Edge)", text=chr(10).join(TXT["10"]))
    finally:
        r.close()
    data["images"] = manifest
    (OUT / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("controls added")


def main():
    if "--controls" in sys.argv:
        return controls()
    OUT.mkdir(parents=True, exist_ok=True)
    r = Renderer(port=9371)
    try:
        def save_render(case, file, html, w, h, how, **extra):
            r.render(html, w, h).save(OUT / file)
            add(case, file, how + f" ({w}×{h}, headless Edge)", **extra)

        save_render("TC-IMG-02", "img02_urdu_internet.png", text_block(TXT["02"], "ur", 46), 1200, 600,
                    "Rendered Urdu, black on white, Noto Nastaliq Urdu 46 px", text=TXT["02"])
        save_render("TC-IMG-07", "img07_roman_internet.png", text_block(TXT["07"], "la", 46), 1200, 600,
                    "Rendered Roman Urdu, black on white, Segoe UI 46 px", text=TXT["07"])
        save_render("TC-IMG-08", "img08_english_textbooks.png", text_block(TXT["08"], "la", 48), 1200, 600,
                    "Rendered English, black on white, Segoe UI 48 px", text=TXT["08"])
        mixed = TXT["09"].replace("petrol", "<span class='la' style='font-size:40px'>petrol</span>")
        save_render("TC-IMG-09", "img09_mixed_petrol.png", text_block(mixed, "ur", 46), 1200, 600,
                    "Rendered mixed Urdu + Latin 'petrol', black on white", text=TXT["09"])
        para = "".join(f"<div>{line}</div>" for line in TXT["10"])
        save_render("TC-IMG-10", "img10_urdu_paragraph.png",
                    f"<div style='width:1200px;height:600px;background:#fff;display:flex;align-items:center;justify-content:center'>"
                    f"<div class='ur' style='font-size:40px;line-height:1.75;text-align:right;width:1040px'>{para}</div></div>", 1200, 600,
                    "Rendered 4-line Urdu paragraph, right-aligned, Noto Nastaliq 40 px", text="\n".join(TXT["10"]))
        base02 = Image.open(OUT / "img02_urdu_internet.png")
        base02.filter(ImageFilter.GaussianBlur(5)).save(OUT / "img11a_blurred.png")
        add("TC-IMG-11", "img11a_blurred.png", "img02_urdu_internet.png with Pillow GaussianBlur(radius=5)", text=TXT["02"])
        save_render("TC-IMG-11", "img11b_light_grey.png", text_block(TXT["02"], "ur", 46, color="#dcdcdc"), 1200, 600,
                    "Rendered TC-IMG-02 text in light grey #dcdcdc on white", text=TXT["02"])

        land = landscape()
        land.save(OUT / "photo_landscape.jpg", quality=90)
        add("TC-IMG-03", "photo_landscape.jpg", "SYNTHETIC photo-like landscape (numpy: sky gradient, sun glow, noisy hills), 1024×768, JPEG q90")
        cap = r.render(f"<div style='width:1024px;height:140px;background:#8b1a1a;display:flex;align-items:center;justify-content:center'>"
                       f"<div class='ur' style='font-size:44px;color:#fff'>{TXT['12']}</div></div>", 1024, 140)
        combo = Image.new("RGB", (1024, 768 + 140)); combo.paste(land, (0, 0)); combo.paste(cap, (0, 768))
        combo.save(OUT / "img12_photo_caption.jpg", quality=90)
        add("TC-IMG-12", "img12_photo_caption.jpg", "SYNTHETIC landscape with an Edge-rendered white Urdu caption on a dark-red strip at the bottom, 1024×908, JPEG q90", text=TXT["12"])

        bg = landscape(1080, 520)
        card = (f"<div style='width:1080px;height:1080px;background:#f2f3f5;font-family:Segoe UI'>"
                f"<div style='height:110px;background:#123a6b;color:#fff;display:flex;align-items:center;padding:0 40px;font-size:40px;font-weight:700'>Daily Update · خبریں</div>"
                f"<div class='ur' style='font-size:52px;line-height:1.8;padding:30px 50px;text-align:right;color:#111'>{TXT['13']}</div>"
                f"<img src='{data_url(bg)}' style='display:block;width:1000px;height:480px;margin:0 40px;object-fit:cover'>"
                f"<div style='padding:20px 40px;color:#666;font-size:28px'>2 hours ago · 1.2K shares</div></div>")
        save_render("TC-IMG-13", "img13_news_card.png", card, 1080, 1080,
                    "Screenshot-style news post: generic header bar ('Daily Update', no real brand), Urdu headline, synthetic photo, footer", text=TXT["13"])

        ai = ai_look(); ai.save(OUT / "photo_ai_look.png")
        add("TC-IMG-14", "photo_ai_look.png", "SYNTHETIC smooth pastel gradient with blurred glowing circles (computer-made look, no text), 1024×1024 PNG")

        meme_bg = street()
        meme = (f"<div style='width:1024px;height:768px;background:url({data_url(meme_bg)}) center/cover;position:relative;font-family:Impact, Arial Black, sans-serif'>"
                + "".join(f"<div style='position:absolute;left:0;right:0;{pos};text-align:center;color:#fff;font-size:58px;"
                          f"-webkit-text-stroke:3px #000;paint-order:stroke fill;text-transform:uppercase'>{t}</div>"
                          for t, pos in zip(TXT["15"], ("top:20px", "bottom:20px"))) + "</div>")
        r.render(meme, 1024, 768).save(OUT / "img15_meme_roman.jpg", quality=90)
        add("TC-IMG-15", "img15_meme_roman.jpg", "SYNTHETIC street scene with Edge-rendered Roman Urdu meme text (white, black outline) at top and bottom, 1024×768 JPEG", text=" / ".join(TXT["15"]))

        for name, img, how in [("photo_street.jpg", meme_bg, "SYNTHETIC street scene (rectangles with windows, noise), 1024×768"),
                               ("photo_texture.jpg", texture(), "SYNTHETIC multi-scale noise texture (rock-like), 1024×768"),
                               ("photo_portrait.jpg", portrait(), "SYNTHETIC portrait-like figure (ellipse face, shapes, blur, noise), 768×1024")]:
            img.save(OUT / name, quality=90)
            add("probe", name, how + ", JPEG q90 (extra asset for the TC-IMG-32/33 detector search)")

        # format cases
        land.resize((64, 64), Image.LANCZOS).save(OUT / "f01_64x64.png")
        add("TC-IMG-01", "f01_64x64.png", "SYNTHETIC landscape resized to 64×64 PNG")
        land.save(OUT / "f16_valid.jpg", "JPEG", quality=88)
        add("TC-IMG-16", "f16_valid.jpg", "SYNTHETIC landscape, baseline JPEG q88")
        street().save(OUT / "f17_valid.webp", "WEBP", quality=85)
        add("TC-IMG-17", "f17_valid.webp", "SYNTHETIC street scene, WEBP q85")
        rgba = Image.open(OUT / "img07_roman_internet.png").convert("RGBA"); rgba.putalpha(150)
        rgba.save(OUT / "f18_alpha.png")
        add("TC-IMG-18", "f18_alpha.png", "img07 (Roman Urdu text) as RGBA PNG with alpha 150/255")
        land.convert("L").save(OUT / "f19_greyscale.jpg", quality=90)
        add("TC-IMG-19", "f19_greyscale.jpg", "SYNTHETIC landscape as 8-bit greyscale (mode L) JPEG")
        Image.new("RGB", (1, 1), (120, 160, 200)).save(OUT / "f20_1x1.png")
        add("TC-IMG-20", "f20_1x1.png", "1×1 PNG")
        big = Image.fromarray(np.tile((np.linspace(60, 200, 8000)[None, :, None] * np.ones((1, 1, 3))).astype(np.uint8), (8000, 1, 1)))
        big.save(OUT / "f21_8000x8000.png", optimize=True)
        add("TC-IMG-21", "f21_8000x8000.png", "8000×8000 horizontal gradient PNG (64 Mpx, compresses well)")
        big.resize((6000, 6000)).save(OUT / "f21b_6000x6000.png", optimize=True)
        add("TC-IMG-21", "f21b_6000x6000.png", "6000×6000 gradient PNG (36 Mpx, under the 40 Mpx cap) — extra, to measure processing time and RAM")
        limit = 10 * 1024 * 1024
        for name, target in (("f22a_just_under_10mb.png", limit - 6000), ("f22b_just_over_10mb.png", limit + 6000)):
            side = int((target / 3) ** 0.5)
            raw = rng.integers(0, 256, (side, side, 3), dtype=np.uint8)
            Image.fromarray(raw).save(OUT / name, compress_level=0)
            size = (OUT / name).stat().st_size
            pad = target - size     # pad with a private PNG chunk to land a few KB from the limit
            data = (OUT / name).read_bytes()
            if pad > 12:
                import zlib
                body = b"Comment\0" + b"x" * (pad - 20)
                chunk = len(body).to_bytes(4, "big") + b"tEXt" + body + zlib.crc32(b"tEXt" + body).to_bytes(4, "big")
                data = data[:-12] + chunk + data[-12:]
                (OUT / name).write_bytes(data)
            add("TC-IMG-22", name, f"random-noise PNG (no compression) padded with a tEXt chunk to {target - limit:+d} bytes from 10 MiB ({limit} bytes)")
        Image.open(OUT / "img08_english_textbooks.png").save(OUT / "f23.gif")
        add("TC-IMG-23", "f23.gif", "img08 (English text) saved as GIF")
        full = jpeg_bytes(land, 90)
        (OUT / "f24_truncated.jpg").write_bytes(full[: len(full) // 2])
        add("TC-IMG-24", "f24_truncated.jpg", "SYNTHETIC landscape JPEG cut to half its bytes")
        (OUT / "f25_png_named.jpg").write_bytes((OUT / "img07_roman_internet.png").read_bytes())
        add("TC-IMG-25", "f25_png_named.jpg", "img07 PNG bytes in a file named .jpg (sent as image/jpeg)")
        upright = r.render(text_block(TXT["02"], "ur", 44, w=600, h=900), 600, 900)
        stored = upright.rotate(90, expand=True)          # 900×600 stored sideways (counter-clockwise)
        exif = Image.Exif(); exif[0x0112] = 6               # Orientation 6: rotate 90° clockwise to display
        stored.save(OUT / "f26_exif6.jpg", "JPEG", quality=92, exif=exif.tobytes())
        add("TC-IMG-26", "f26_exif6.jpg", "Urdu TC-IMG-02 text rendered upright 600×900, stored rotated 900×600 with EXIF Orientation 6", text=TXT["02"],
            upright_size=[600, 900])
        (OUT / "f04_text_renamed.png").write_text("This is a plain text file, not an image.\n" * 20, encoding="utf-8")
        add("TC-IMG-04", "f04_text_renamed.png", "plain text file renamed to .png")
        Image.open(OUT / "img08_english_textbooks.png").save(OUT / "f04_document.pdf", "PDF")
        add("TC-IMG-04", "f04_document.pdf", "img08 saved as a one-page PDF by Pillow")
    finally:
        r.close()
    fixture = HERE.parents[0] / "fixtures" / "urdu_headline.png"
    manifest.append({"case": "TC-IMG-06", "file": "../../fixtures/urdu_headline.png", "how_made": "existing repo fixture (unchanged)",
                     "bytes": fixture.stat().st_size, "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()})
    (OUT / "manifest.json").write_text(json.dumps({
        "_note": "All assets made locally for the image test cases; nothing downloaded, no real user upload used. "
                 "Urdu text rendered by headless Edge with Noto Nastaliq Urdu (node_modules/@expo-google-fonts); "
                 "photo-like images are SYNTHETIC.", "font_urdu": str(FONT.relative_to(FRONTEND)), "images": manifest},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(manifest)} assets in {OUT}")


if __name__ == "__main__":
    main()
