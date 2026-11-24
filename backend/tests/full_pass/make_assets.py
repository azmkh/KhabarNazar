"""Build the full-pass test inputs: text_inputs.json and images/ with manifest.json.

Run once from backend/ (re-running rebuilds the same files):

    .\\.venv\\Scripts\\python.exe tests\\full_pass\\make_assets.py

All sentences are original synthetic text written for this test pass (not real news) and have no
ground-truth label: the pass checks behaviour, not accuracy.

Text images are drawn by headless Microsoft Edge from small HTML pages, because the installed
Pillow has no libraqm, so Pillow alone draws Urdu letters unjoined and in the wrong order (which
would test a broken rendering instead of OCR). Pillow then adds blur, low contrast, rotation and
EXIF tags. Photos come from generated pictures or from the local backend/uploads folder (copied as
images/local_*.jpg, git-ignored: they are web pictures, not ours to publish). Nothing is downloaded.
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
IMAGES = HERE / "images"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

# ─── Text inputs ─────────────────────────────────────────────────────────────

URDU_POOL_CREDIBLE = [
    "شہر کی بلدیہ نے پانی کی فراہمی بہتر بنانے کے لیے ایک نیا منصوبہ شروع کیا ہے۔",
    "منصوبے کے تحت پرانی پائپ لائنوں کو مرحلہ وار تبدیل کیا جائے گا۔",
    "حکام کے مطابق پہلا مرحلہ تین مہینوں میں مکمل ہونے کی توقع ہے۔",
    "اس دوران کچھ علاقوں میں پانی کی فراہمی چند گھنٹوں کے لیے معطل رہ سکتی ہے۔",
    "شہریوں کو ہدایت کی گئی ہے کہ وہ پانی ذخیرہ کرنے کا پہلے سے انتظام کر لیں۔",
    "بلدیہ کے ترجمان نے بتایا کہ منصوبے کے لیے رقم صوبائی بجٹ سے فراہم کی گئی ہے۔",
    "ماہرین کا کہنا ہے کہ پرانی لائنوں سے روزانہ بڑی مقدار میں پانی ضائع ہو رہا تھا۔",
    "نئی لائنوں کی تنصیب کے بعد پانی کے دباؤ میں بھی بہتری متوقع ہے۔",
    "مقامی تاجروں نے منصوبے کا خیرمقدم کیا ہے لیکن کام کے دوران ٹریفک کے مسائل پر تشویش ظاہر کی ہے۔",
    "انتظامیہ نے متبادل راستوں کی نشاندہی کے لیے ٹریفک پولیس سے رابطہ کیا ہے۔",
    "منصوبے کی نگرانی کے لیے ایک کمیٹی بنائی گئی ہے جو ہر ہفتے رپورٹ پیش کرے گی۔",
    "شہری اپنی شکایات بلدیہ کے ہیلپ لائن نمبر پر درج کروا سکتے ہیں۔",
    "ترجمان کے مطابق کام زیادہ تر رات کے اوقات میں کیا جائے گا تاکہ کاروبار متاثر نہ ہو۔",
]
URDU_POOL_FAKE_STYLE = [
    "سوشل میڈیا پر ایک پیغام تیزی سے پھیل رہا ہے جس میں دعویٰ کیا گیا ہے کہ ایک خفیہ دوا ہر بیماری کا علاج کر سکتی ہے۔",
    "پیغام کے مطابق یہ دوا صرف ایک دن میں شوگر، بلڈ پریشر اور دل کے امراض ختم کر دیتی ہے۔",
    "پیغام بھیجنے والوں کا کہنا ہے کہ ڈاکٹر اس دوا کو جان بوجھ کر چھپا رہے ہیں۔",
    "دعویٰ کیا گیا ہے کہ دوا گھر میں عام چیزوں سے تیار کی جا سکتی ہے اور اس کا کوئی نقصان نہیں۔",
    "پیغام میں لوگوں سے کہا گیا ہے کہ وہ اپنی تمام ادویات فوراً چھوڑ دیں اور صرف یہی نسخہ استعمال کریں۔",
    "ساتھ ہی لکھا ہے کہ اگر یہ پیغام دس لوگوں کو نہ بھیجا گیا تو بدقسمتی آ سکتی ہے۔",
    "پیغام میں کسی ہسپتال، تحقیق یا ماہر کا نام نہیں دیا گیا۔",
    "کئی لوگوں نے بغیر تصدیق کے یہ پیغام اپنے خاندان کے گروپوں میں آگے بھیج دیا ہے۔",
    "پیغام کے آخر میں ایک نامعلوم نمبر دیا گیا ہے جس پر رقم بھیج کر دوا منگوانے کا کہا گیا ہے۔",
    "دعویٰ کرنے والوں کا کہنا ہے کہ حکومت جلد اس دوا پر پابندی لگا دے گی اس لیے ابھی خرید لیں۔",
    "پیغام کے ساتھ ایک تصویر بھی لگائی گئی ہے جس کا اس دوا سے کوئی تعلق ثابت نہیں ہوتا۔",
    "اس پیغام کو پڑھنے والوں سے کہا گیا ہے کہ وہ اسے فوراً اپنے تمام رابطوں کو بھیج دیں۔",
]
NUMBER_HEAVY = [
    "سال ۲۰۲۴ میں ۱۲۳۴۵۶۷ روپے کی لاگت سے ۸۹۰۱۲ گھروں کو ۳۴۵۶۷۸ لیٹر پانی ملا۔",
    "رپورٹ نمبر ۵۶۷۸۹۰۱ کے مطابق ۲۳۴۵۶ شکایات میں سے ۱۹۸۷۶ حل ہو چکی ہیں۔",
    "منصوبہ ۷۶۵۴۳۲۱ اور منصوبہ ۱۰۲۹۳۸۴ کی رقم ۴۵۶۷۸۹۰۱۲ روپے بتائی گئی ہے۔",
    "شمارہ ۹۸۷۶۵۴ میں ۱۲۰۳۴۵ صارفین اور ۶۷۸۹۰۱ کنکشنز کا ذکر ہے۔",
]


def words(pool: list[str], count: int) -> str:
    """Exactly `count` whitespace-separated words, taken from the pool in order (repeating it)."""
    out: list[str] = []
    i = 0
    while len(out) < count:
        out.extend(pool[i % len(pool)].split())
        i += 1
    return " ".join(out[:count])


def token_count(text: str) -> int:
    """Tokens the Urdu XLM-R reads for `text` (its tokenizer after its own cleaning; no inference)."""
    sys.path.insert(0, str(BACKEND))
    from transformers import AutoTokenizer

    from app.ai.text.preprocess import clean_urdu_notebook
    from app.ai.text.xlmr import model_dir

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir("urdu")), local_files_only=True)
    return len(tokenizer(clean_urdu_notebook(text))["input_ids"])


def truncation_case() -> tuple[str, int, int]:
    """Urdu under 150 words whose cleaned text is longer than 256 XLM-R tokens."""
    sentences: list[str] = []
    i = 0
    while True:
        sentences.append(NUMBER_HEAVY[i % len(NUMBER_HEAVY)])
        text = " ".join(sentences)
        n_words, n_tokens = len(text.split()), token_count(text)
        if n_tokens > 270:
            return text, n_words, n_tokens
        if n_words >= 149:
            raise SystemExit("could not build a <150-word text with >256 tokens")
        i += 1


ROMAN_10K = ("Hukoomat ne aaj elan kiya hai ke shehar mein naye bus routes shuru kiye jayenge aur "
             "kiraya bhi kam rakha jayega. ")


def text_inputs() -> list[dict]:
    U, R, T, N = "xlmr-urdu", "xlmr-roman-urdu", "tfidf-urdu-long-articles", "text-model-unavailable"
    long_tf = words(URDU_POOL_FAKE_STYLE + URDU_POOL_CREDIBLE, 200)
    trunc_text, trunc_words, trunc_tokens = truncation_case()
    ten_k = (ROMAN_10K * 200)[:10_000]
    assert len(ten_k.strip()) == 10_000, "10,000-character case must survive strip()"
    ten_k = ten_k[:-1] + "a" if ten_k.endswith(" ") else ten_k

    def item(id_, cat, text, route, outcome="accepted", language=None, disclosure=None, note="", tc=None):
        return {"id": id_, "category": cat, "text": text,
                "expected": {"outcome": outcome, "model_version": route, "detected_language": language,
                             "disclosure": disclosure or []},
                "note": note, "report_tc": tc}

    rows = [
        # Urdu short
        item("U01", "urdu_short", "حکومت نے آج اعلان کیا ہے کہ یکم نومبر سے تمام سرکاری اسکولوں میں مفت کتابیں فراہم کی جائیں گی۔", U, language="urdu", note="given sentence; pair of R01", tc="TC-TXT-02"),
        item("U02", "urdu_short", "حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔", U, language="urdu", note="given sentence; pair of R02"),
        item("U03", "urdu_short", "شہر میں نئے ہسپتال کی تعمیر کا کام اگلے مہینے مکمل ہو جائے گا۔", U, language="urdu", note="credible style"),
        item("U04", "urdu_short", "سائنسدانوں نے دریافت کیا ہے کہ روزانہ پیاز کھانے سے ہر بیماری ختم ہو جاتی ہے۔", U, language="urdu", note="fake style"),
        item("U05", "urdu_short", "فوری خبر! کل سے ملک کے تمام بینک ایک مہینے کے لیے بند رہیں گے، فوراً اپنی رقم نکال لیں۔", U, language="urdu", note="fake style"),
        # Urdu long
        item("UL1", "urdu_long", long_tf, T, language="urdu", disclosure=["Long articles are checked as a whole"], note="200 words", tc="TC-TXT-03"),
        item("UL2", "urdu_long", words(URDU_POOL_CREDIBLE, 149), U, language="urdu", note="149 words: just below the cutoff (XLM-R)"),
        item("UL3", "urdu_long", words(URDU_POOL_CREDIBLE, 151), T, language="urdu", disclosure=["Long articles are checked as a whole"], note="151 words: just above the cutoff (TF-IDF)"),
        item("UL4", "urdu_long", trunc_text, U, language="urdu", disclosure=["only its first part was checked"],
             note=f"{trunc_words} words but {trunc_tokens} XLM-R tokens after cleaning (limit 256): truncated"),
        # Roman Urdu
        item("R01", "roman_urdu", "Hukoomat ne aaj elan kiya hai ke 1 November se tamam sarkari schools mein muft kitaabein faraham ki jayengi.", R, language="roman_urdu", note="pair of U01", tc="TC-TXT-04"),
        item("R02", "roman_urdu", "Hukoomat ne elan kiya hai ke mulk bhar mein saat din ke liye internet service band kar di jayegi.", R, language="roman_urdu", note="pair of U02"),
        item("R03", "roman_urdu", "Hukoomat ne petrol ki qeemat mein 20 rupay kami ka elan kar diya hai ke yeh kal se lagu hogi.", R, language="roman_urdu", note="spelling A of one claim"),
        item("R04", "roman_urdu", "Hakumat ne petrol ki qimat me 20 rupay kami ka elaan kar dia he k yeh kal se lagu hogi.", R, language="roman_urdu", note="spelling B of the same claim"),
        item("R05", "roman_urdu", "Hkumat ne petrol ki keemat mai 20 rupe kmi ka elan kr diya hai k ye kal se lagu hogi.", R, language="roman_urdu", note="spelling C of the same claim"),
        item("R06", "roman_urdu", "Social media par khabar phail rahi hai ke kal raat shehar mein zalzala aaya tha lekin mehkama mosamiat ne tasdeeq nahi ki.", R, language="roman_urdu"),
        item("R07", "roman_urdu", "Lahore mein aaj subah halki barish hui aur mosam khushgawar ho gaya, mehkama ne kal bhi barish ka imkan zahir kiya hai.", R, language="roman_urdu", note="credible style"),
        # English
        item("E01", "english", "The government has announced that all schools will remain closed for a week because of heavy rain.", R, language="english", disclosure=["results for English text are less reliable"], tc="TC-TXT-05"),
        item("E02", "english", "Scientists have confirmed that drinking hot water with lemon cures every disease within a day.", R, language="english", disclosure=["results for English text are less reliable"]),
        item("E03", "english", "The city council said that the new bus route will start operating from next Monday morning.", R, language="english", disclosure=["results for English text are less reliable"]),
        # Mixed
        item("M01", "mixed", "حکومت نے نئی ٹیکس پالیسی کا اعلان کیا ہے جس کے تحت online shopping پر اضافی tax لگایا جائے گا۔", U, language="urdu", note="mostly Urdu letters (>=70%) with English words"),
        item("M02", "mixed", "Breaking news: government ne petrol ki price 50 rupees barha di hai, according to sources yeh kal se lagu hogi.", R, language="roman_urdu", note="Roman Urdu with English"),
        item("M03", "mixed", "حکومت نے اعلان کیا hai ke kal se tamam schools band rahenge aur imtihanat agle mahine honge", R, language="mixed", disclosure=["mixes Urdu and English script"], note="Urdu script + Roman Urdu, Urdu letters < 50%"),
        item("M04", "mixed", "حُکُومَت نے اِعلان کِیا ہے کہ اَگلے ہَفتے سے بِجلی کی قِیمَت کَم ہو جائے گی۔", U, language="urdu", note="Urdu with diacritics (zabar/zer/pesh)"),
        item("M05", "mixed", "حکومت نے ۱۵ دسمبر سے ۲۰ فیصد سستی بجلی کا اعلان کیا ہے، ٣٠ لاکھ صارفین مستفید ہوں گے۔", U, language="urdu", note="Urdu (U+06F0) and Arabic-Indic (U+0660) digits"),
        item("M06", "mixed", "🚨 فوری خبر 🚨 کل سے ملک بھر میں پٹرول پمپ بند رہیں گے 😱🔥", U, language="urdu", note="Urdu with emoji"),
        # Other languages
        item("O01", "other_language", "أعلنت الحكومة اليوم عن إغلاق جميع المدارس لمدة أسبوع بسبب الأمطار الغزيرة في البلاد.", None, note="Arabic: Arabic script; record the route"),
        item("O02", "other_language", "دولت امروز اعلام کرد که همه مدارس به مدت یک هفته تعطیل خواهند شد.", None, note="Persian: Arabic script; record the route"),
        item("O03", "other_language", "सरकार ने आज घोषणा की कि सभी स्कूल एक हफ्ते के लिए बंद रहेंगे।", None, note="Hindi (Devanagari); record the route"),
        # Not news
        item("N01", "not_news", "بریانی بنانے کے لیے پہلے چاول بھگو دیں، پھر پیاز سنہری ہونے تک تلیں اور مصالحہ ڈال کر دم پر رکھ دیں۔", U, language="urdu", note="recipe; use case 3-B expects 'does not appear to be news'"),
        item("N02", "not_news", "عید مبارک! آپ کو اور آپ کے پورے خاندان کو دل کی گہرائیوں سے مبارکباد۔", U, language="urdu", note="greeting; use case 3-B"),
        # Edge and bad input
        item("X01", "edge", "", None, outcome="rejected_422", note="empty", tc="TC-TXT-06"),
        item("X02", "edge", "     \n\t  ", None, outcome="rejected_422", note="whitespace only"),
        item("X03", "edge", "ab", None, outcome="rejected_422", note="2 characters, below the 3-character minimum"),
        item("X04", "edge", "خبر", U, language="urdu", note="exactly 3 characters"),
        item("X05", "edge", ten_k, R, language="roman_urdu", disclosure=["only its first part was checked"], note="exactly 10,000 characters (Roman Urdu, beyond 512 tokens)"),
        item("X06", "edge", ten_k + "b", None, outcome="rejected_422", note="10,001 characters"),
        item("X07", "edge", "😀😀😀🎉🎉", N, outcome="uncertain_no_score", note="emoji only (no letters)"),
        item("X08", "edge", "1234567890", N, outcome="uncertain_no_score", note="digits only"),
        item("X09", "edge", "https://example.com/news/2026/11/24/story-12345", N, outcome="uncertain_no_score",
             note="URL only: the test plan expects Uncertain; the URL does contain letters"),
        item("X10", "edge", "<script>alert('x')</script><b>حکومت نے</b> آج <i>نئی</i> پالیسی کا اعلان کیا ہے", U, language="mixed",
             note="HTML/script tags: must be stored and returned as plain text"),
        item("X11", "edge", "حکومت\u200b نے\u200c آج\u200d اعلان\ufeff کیا ہے کہ کل چھٹی ہوگی", U, language="urdu",
             note="zero-width space, non-joiner, joiner and BOM inside the text"),
        item("X12", "edge", "'; DROP TABLE submissions; -- hukoomat ne elan kiya hai ke kal chutti hogi", R, language="roman_urdu",
             note="SQL-injection-style text: stored verbatim, tables unaffected"),
    ]
    return rows


# ─── Images ──────────────────────────────────────────────────────────────────

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:{bg};}}
.box{{width:{w}px;height:{h}px;display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:30px;}}
.t{{font-family:{font};font-size:{size}px;color:{fg};line-height:1.5;text-align:center;direction:{dir};font-weight:{weight};}}
</style></head><body><div class="box"><div class="t">{text}</div></div></body></html>"""


def render_text(name: str, text: str, w=1000, h=400, size=56, fg="#111", bg="#fff", rtl=False,
                font="'Segoe UI', Tahoma, Arial", weight=600) -> Image.Image:
    """Render text with headless Edge (correct Urdu shaping) and return it as an RGB image."""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / f"{name}.html"
        page.write_text(HTML.format(bg=bg, fg=fg, w=w, h=h, size=size, font=font, weight=weight,
                                    dir="rtl" if rtl else "ltr", text=text), encoding="utf-8")
        shot = Path(tmp) / f"{name}.png"
        subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        f"--user-data-dir={Path(tmp) / 'profile'}",
                        "--force-device-scale-factor=1", f"--window-size={w},{h}",
                        f"--screenshot={shot}", page.as_uri()],
                       check=True, capture_output=True, timeout=60)
        return Image.open(shot).convert("RGB").crop((0, 0, w, h))


def noise_png(width: int, height: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    img = Image.frombytes("RGB", (width, height), rnd.randbytes(width * height * 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=0)
    return buf.getvalue()


def sized_png(target: int, seed: int) -> bytes:
    """An uncompressed noise PNG of about `target` bytes (square)."""
    side = int((target / 3) ** 0.5)
    data = noise_png(side, side, seed)
    while len(data) > target:
        side -= 2
        data = noise_png(side, side, seed)
    return data


def jpeg_bytes(img: Image.Image, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, **kw)
    return buf.getvalue()


def local_upload(prefix: str) -> Path:
    found = sorted((BACKEND / "uploads").glob(prefix + "*"))
    if not found:
        raise SystemExit(f"backend/uploads/{prefix}* is missing")
    return found[0]


def build_images() -> list[dict]:
    if IMAGES.exists():
        shutil.rmtree(IMAGES)
    IMAGES.mkdir(parents=True)
    (IMAGES / ".gitignore").write_text("# copies of local web pictures; not ours to publish\nlocal_*\n", encoding="utf-8")
    manifest: list[dict] = []

    def save(id_, filename, data_or_img, how, expect, category, content_type=None, tc=None, **save_kw):
        path = IMAGES / filename
        if isinstance(data_or_img, Image.Image):
            fmt = save_kw.pop("format", None)
            data_or_img.save(path, format=fmt, **save_kw)
        else:
            path.write_bytes(data_or_img)
        data = path.read_bytes()
        manifest.append({"id": id_, "file": filename, "category": category, "how_made": how,
                         "content_type": content_type or {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                                                          ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf"}
                         .get(path.suffix.lower(), "application/octet-stream"),
                         "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "expected": expect,
                         "report_tc": tc})

    urdu = render_text("urdu", "حکومت نے ملک بھر میں انٹرنیٹ سروس سات دن کے لیے بند کرنے کا اعلان کر دیا", rtl=True, size=54)
    roman = render_text("roman", "Hukoomat ne mulk bhar mein internet service saat din ke liye band karne ka elan kar diya", size=50)
    english = render_text("english", "Government announces that all schools will remain closed for a week", size=54)
    mixed = render_text("mixed", "BREAKING: حکومت نے پٹرول کی قیمت میں کمی کا اعلان کر دیا<br>Petrol price cut from tomorrow", size=46)
    para = render_text("para", "Pehli line: hukoomat ne naya budget pesh kar diya hai<br>Doosri line: is mein taleem ke liye zyada raqam rakhi gayi<br>Teesri line: sehat ka budget bhi barha diya gaya hai",
                       w=1100, h=420, size=40, weight=500)
    low = render_text("low", "Hukoomat ne kal se tamam schools band karne ka elan kiya hai", size=44, fg="#c9c9c9", bg="#d6d6d6", weight=400)
    low = low.filter(ImageFilter.GaussianBlur(2.2))

    common = {"category": "content"}
    accept_text = {"http_status": 201, "analysis_branch": "image_pair", "ocr_status": "completed"}
    save("C01", "urdu_headline.png", urdu, "Edge-rendered Urdu headline, black on white, Segoe UI", accept_text | {"route": "xlmr-urdu"}, tc="TC-IMG-02", **common)
    save("C02", "roman_headline.png", roman, "Edge-rendered Roman Urdu headline", accept_text | {"route": "xlmr-roman-urdu"}, tc="TC-IMG-03", **common)
    save("C03", "english_headline.png", english, "Edge-rendered English headline", accept_text | {"route": "xlmr-roman-urdu", "disclosure": "English"}, **common)
    save("C04", "mixed_scripts.png", mixed, "Edge-rendered: one Urdu line and one English line", accept_text, **common)
    save("C05", "multiline_paragraph.png", para, "Edge-rendered: three numbered Roman Urdu lines (Pehli/Doosri/Teesri)", accept_text | {"reading_order": ["Pehli", "Doosri", "Teesri"]}, **common)
    save("C06", "low_contrast_blurred.png", low, "Edge-rendered light-grey text on grey, Gaussian blur r=2.2 (aims near the OCR cutoff)",
         {"http_status": 201, "note": "either branch is acceptable; the reason must be consistent with ocr_status/confidence"}, **common)

    fox = local_upload("393c64a1")
    shutil.copyfile(fox, IMAGES / "local_fox_no_text.jpg")
    data = (IMAGES / "local_fox_no_text.jpg").read_bytes()
    manifest.append({"id": "C07", "file": "local_fox_no_text.jpg", "category": "content", "how_made": f"copy of backend/uploads/{fox.name} (fox picture, no text)",
                     "content_type": "image/jpeg", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                     "expected": {"http_status": 201, "analysis_branch": "ai_or_real", "final_label": "Uncertain", "combined_risk_score": None},
                     "report_tc": "TC-IMG-01"})

    wildebeest = Image.open(local_upload("a4dea7e0")).convert("RGB")
    photo = wildebeest.crop((0, 0, wildebeest.width, int(wildebeest.height * 0.9)))  # drop the stock watermark strip
    photo = photo.resize((photo.width * 2, photo.height * 2))
    bar = render_text("caption", "جنگلی جانوروں کی تعداد میں اضافہ، محکمہ جنگلات کی رپورٹ", w=photo.width, h=110, size=40, fg="#fff", bg="#b00020", rtl=True)
    captioned = Image.new("RGB", (photo.width, photo.height + bar.height))
    captioned.paste(photo, (0, 0))
    captioned.paste(bar, (0, photo.height))
    save("C08", "local_photo_caption_bar.jpg", captioned, "local wildebeest photo (watermark strip cut off, 2x) with an Edge-rendered red Urdu caption bar below", accept_text, format="JPEG", quality=90, **common)

    roses = Image.open(local_upload("a72e3aca")).convert("RGB").resize((582, 582))
    top = render_text("memetop", "JAB DOST KEHTA HAI", w=582, h=90, size=44, fg="#fff", bg="#000", font="Impact, Arial Black", weight=400)
    bottom = render_text("memebottom", "bas 5 minute mein aa raha hoon", w=582, h=90, size=38, fg="#fff", bg="#000", font="Impact, Arial Black", weight=400)
    meme = Image.new("RGB", (582, 762))
    meme.paste(top, (0, 0)); meme.paste(roses, (0, 90)); meme.paste(bottom, (0, 672))
    save("C09", "local_meme.jpg", meme, "local roses picture with black Roman Urdu meme bars above and below", {"http_status": 201}, format="JPEG", quality=90, **common)

    rnd = random.Random(7)
    synth = Image.new("RGB", (768, 768))
    draw = ImageDraw.Draw(synth)
    for y in range(768):
        draw.line([(0, y), (767, y)], fill=(40 + y // 6, 20 + y // 10, 120 + y // 8))
    for _ in range(14):
        x, y, r = rnd.randrange(768), rnd.randrange(768), rnd.randrange(30, 140)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(rnd.randrange(150, 255), rnd.randrange(80, 200), rnd.randrange(120, 255)))
    synth = synth.filter(ImageFilter.GaussianBlur(6))
    save("C10", "synthetic_render.png", synth, "generated: gradient with blurred glowing circles (computer-made, no text)",
         {"http_status": 201, "analysis_branch": "ai_or_real"}, **common)
    roses_path = IMAGES / "local_roses_ai_look.jpg"
    shutil.copyfile(local_upload("a72e3aca"), roses_path)
    d = roses_path.read_bytes()
    manifest.append({"id": "C11", "file": roses_path.name, "category": "content", "how_made": "copy of a local picture of roses with an AI-generated look",
                     "content_type": "image/jpeg", "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest(),
                     "expected": {"http_status": 201, "analysis_branch": "ai_or_real"}, "report_tc": None})

    # Formats
    f = {"category": "format"}
    base = english.resize((800, 320))
    save("F01", "format_jpeg.jpg", base, "English headline saved as JPEG", {"http_status": 201}, format="JPEG", quality=90, **f)
    save("F02", "format_png.png", base, "English headline saved as PNG", {"http_status": 201}, **f)
    save("F03", "format_webp.webp", base, "English headline saved as WEBP", {"http_status": 201}, format="WEBP", quality=90, **f)
    rgba = base.convert("RGBA"); rgba.putalpha(Image.new("L", rgba.size, 140))
    save("F04", "format_png_transparent.png", rgba, "English headline PNG with alpha 140/255", {"http_status": 201}, **f)
    save("F05", "format_greyscale.png", base.convert("L"), "English headline, 8-bit greyscale PNG", {"http_status": 201}, **f)
    save("F06", "format_1x1.png", Image.new("RGB", (1, 1), (120, 30, 30)), "1x1 pixel PNG", {"http_status": 201, "note": "accepted; record what the pipeline does"}, **f)
    big = Image.new("RGB", (8000, 8000), (200, 210, 220))
    save("F07", "format_8000x8000.png", big, "8000x8000 flat PNG (64 Mpx, small file)", {"http_status": 413, "note": "over MAX_IMAGE_PIXELS (40 Mpx)"}, **f)
    big2 = Image.new("RGB", (6000, 6000), (200, 210, 220)); ImageDraw.Draw(big2).text((100, 100), "x", fill="black")
    save("F07b", "format_6000x6000.png", big2, "6000x6000 flat PNG (36 Mpx, under the pixel cap)", {"http_status": 201}, **f)
    save("F08", "format_just_under_10mb.png", sized_png(10 * 1024 * 1024 - 60_000, 1), "uncompressed noise PNG just under 10 MiB", {"http_status": 201}, **f)
    save("F09", "format_just_over_10mb.png", noise_png(1900, 1900, 3), "uncompressed noise PNG just over 10 MiB", {"http_status": 413}, **f)
    gif = io.BytesIO(); base.convert("P").save(gif, format="GIF")
    save("F10", "format.gif", gif.getvalue(), "English headline as GIF", {"http_status": 415}, **f)
    pdf = io.BytesIO(); base.save(pdf, format="PDF")
    save("F11", "format.pdf", pdf.getvalue(), "English headline as a one-page PDF", {"http_status": 415}, **f)
    save("F12", "text_renamed.png", b"This is a plain text file renamed to .png\n" * 20, "a .txt file renamed to .png", {"http_status": 415}, content_type="image/png", **f)
    full = jpeg_bytes(base)
    save("F13", "truncated.jpg", full[: len(full) // 2], "the JPEG above cut to half its bytes", {"http_status": 415}, **f)
    rotated = urdu.rotate(90, expand=True)  # stored sideways; Orientation 6 says "rotate 90 CW to view"
    exif = Image.Exif(); exif[274] = 6
    save("F14", "exif_orientation_6.jpg", jpeg_bytes(rotated, exif=exif.tobytes()), "Urdu headline stored rotated 90 deg CCW with EXIF Orientation=6 (upright when honoured)",
         {"http_status": 201, "ocr_reads_upright": True}, tc=None, **f)
    png_named_jpg = io.BytesIO(); base.save(png_named_jpg, format="PNG")
    save("F15", "png_content_named.jpg", png_named_jpg.getvalue(), "PNG bytes in a file named .jpg, sent as image/jpeg",
         {"http_status": 201, "mime_type": "image/png"}, content_type="image/jpeg", **f)

    for m in manifest:
        path = IMAGES / m["file"]
        if m["id"] == "F09":
            m["bytes"] = path.stat().st_size
            assert m["bytes"] > 10 * 1024 * 1024, "F09 must be over 10 MiB"
        if m["id"] == "F08":
            assert m["bytes"] < 10 * 1024 * 1024
    (IMAGES / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    rows = text_inputs()
    (HERE / "text_inputs.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"text_inputs.json: {len(rows)} inputs")
    for r in rows:
        if r["category"] == "urdu_long" or r["id"] in ("X04", "X05", "X06"):
            print(f"  {r['id']}: {len(r['text'].split())} words, {len(r['text'])} chars - {r['note']}")
    manifest = build_images()
    print(f"images/manifest.json: {len(manifest)} images")
    for m in manifest:
        print(f"  {m['id']:5} {m['file']:32} {m['bytes']:>10} bytes")
