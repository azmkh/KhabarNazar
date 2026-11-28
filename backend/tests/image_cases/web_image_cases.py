"""Screen checks for the image module: TC-IMG-13 (screen part), 34 (screen part), 40, 41, 42, 43, 44, 45.

    python tests/image_cases/web_image_cases.py --web http://localhost:8082 --api http://127.0.0.1:8001 --run-dir RUN

Headless Microsoft Edge (Chrome DevTools Protocol) at phone size against the Expo web dev server, whose
EXPO_PUBLIC_API_URL is the throwaway backend. Images are picked through the browser's real file chooser.
Run from PowerShell. TC-IMG-44 stops the backend (RUN/server.pid) part-way through a request, so it runs last.
Screenshots go to screens/; results merge into results_<date>.json/.csv.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "full_pass"))
sys.path.insert(0, str(HERE))
from ui_pass import PASSWORD, Browser  # noqa: E402
from run_image_cases import IMAGES, save  # noqa: E402

SCREENS = HERE / "screens"
# constants/theme.ts: news-verdict colours (light, dark) that the authenticity card must NOT use
VERDICT_RGB = {"rgb(21, 128, 61)", "rgb(185, 28, 28)", "rgb(74, 222, 128)", "rgb(248, 113, 113)"}
INFO_RGB = {"rgb(3, 105, 161)", "rgb(56, 189, 248)"}


class WebBrowser(Browser):
    def __init__(self, port):
        self.posts: list[str] = []
        super().__init__(port=port)

    def _event(self, msg):
        if msg.get("method") == "Network.requestWillBeSent":
            req = msg["params"]["request"]
            if req["method"] == "POST" and "/submissions/image" in req["url"]:
                self.posts.append(req["url"])
        super()._event(msg)

    def shot(self, name):
        SCREENS.mkdir(exist_ok=True)
        p = SCREENS / f"{name}.png"
        p.write_bytes(base64.b64decode(self.send("Page.captureScreenshot", format="png")["data"]))
        return f"backend/tests/image_cases/screens/{p.name}"

    def wait_path(self, prefix, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if (self.path() or "").startswith(prefix):
                return True
            self.pump(0.25)
        return False

    def analyze_state(self):
        return self.js("""(() => { const e = [...document.querySelectorAll('[aria-label="Analyze"]')].find(x => x.getBoundingClientRect().width);
            return e ? {ariaDisabled: e.getAttribute('aria-disabled'), spinner: !!e.querySelector('[role=progressbar]')} : null; })()""")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default="http://localhost:8082")
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--port", type=int, default=9381)
    ap.add_argument("--only", action="append", default=[])
    args = ap.parse_args()
    want = lambda cid: not args.only or cid in args.only
    W, API = args.web.rstrip("/"), args.api.rstrip("/") + "/api/v1"
    json_path = HERE / f"results_{args.date}.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    email = f"img.web.{int(time.time())}@example.com"
    token = httpx.post(API + "/auth/register", json={"name": "Image web", "email": email, "password": PASSWORD}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    hist = lambda: len(httpx.get(API + "/submissions?skip=0&limit=100", headers=auth).json())

    def rec(cid, result, evidence, expected, raw, notes=""):
        data["cases"][cid] = {"result": result, "evidence": evidence, "expected": expected, "notes": notes, "raw": raw,
                              "run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "base_url": args.api}
        print(f"{cid:10} {result:16} {evidence}", flush=True)
        save(json_path, data)

    def merge_screen(cid, ok, evidence, raw):
        c = data["cases"].get(cid)
        if not c:
            return rec(cid, "Pass" if ok else "Fail", "screen: " + evidence, "", {"web": raw})
        # Keep the API part's own result, then combine it with this screen check.
        c["raw"].setdefault("api_result", c["result"] if not (c["raw"].get("web") or {}).get("evidence") else c["raw"].get("api_result", "Pass"))
        c["raw"]["web"] = {"ok": ok, "evidence": evidence, **raw}
        base = c["evidence"].split(" · screen")[0]
        c["evidence"] = base + " · screen: " + evidence
        c["result"] = c["raw"]["api_result"] if ok else "Fail"
        print(f"{cid:10} {c['result']:16} {c['evidence']}", flush=True)
        save(json_path, data)

    b = WebBrowser(args.port)

    def check_screen():
        b.go(W + "/", 4)
        b.wait_text("Analyze", 60)
        b.click("Image", wait=1)

    def analyse(file: Path, timeout=180):
        check_screen()
        b.pick_file("Gallery", file)
        b.click("Analyze", wait=0.5)
        ok = b.wait_path("/result/", timeout)
        b.pump(3)
        return ok, (b.path() or "").rsplit("/", 1)[-1]

    def page_facts():
        return b.js(f"""(() => {{ const t = document.body.innerText;
            const auth = [...document.querySelectorAll('div,span')].find(e => e.childElementCount === 0 && e.innerText && e.innerText.trim().toLowerCase().startsWith('image authenticity'));
            const heatCard = [...document.querySelectorAll('div')].reverse().find(e => e.innerText && e.innerText.trim().toLowerCase().startsWith('where the detector looked') && e.querySelector('img'));
            const heatImgs = heatCard ? [...heatCard.querySelectorAll('img')].filter(i => i.src.startsWith('blob:') && i.naturalWidth > 0) : [];
            const lc = t.toLowerCase();
            return {{ verdictAt: lc.indexOf('verdict on the text in the image'), authAt: lc.indexOf('image authenticity'),
                     authColor: auth ? getComputedStyle(auth).color : null, authText: auth ? auth.innerText : null,
                     limitationNote: t.includes('treat this as a hint, not proof'), textImageNote: t.includes('the kind of image the detector most often rates as AI-generated'),
                     heatmapShown: heatImgs.length > 0, heatmapNatural: heatImgs.length ? [heatImgs[0].naturalWidth, heatImgs[0].naturalHeight] : null,
                     resnetCaption: t.includes("Grad-CAM from the detector's ResNet18 model"), ocrShown: lc.includes('text found in image (ocr)'),
                     noClaim: t.includes('No readable news text was found in this image, so no news claim was checked.'),
                     uncertainShown: /uncertain/i.test(t), heatmapMissingNote: t.includes('The heatmap could not be produced') }}; }})()""")

    try:
        b.go(W + "/login", 8)
        b.wait_text("Welcome back", 120)
        b.type("you@example.com", email); b.type("Your password", PASSWORD)
        b.click("Sign in", wait=3)
        b.wait_text("Analyze", 60)

        if want("TC-IMG-13") or want("TC-IMG-42") or want("TC-IMG-34"):
            ok, sid = analyse(IMAGES / "img13_news_card.png")
            f = page_facts()
            s1 = b.shot("TC-IMG-13_42_result_top")
            b.js("window.scrollBy(0, 700)"); b.pump(0.8)
            s2 = b.shot("TC-IMG-13_42_result_heatmap")
            b.js("window.scrollBy(0, 900)"); b.pump(0.8)
            s3 = b.shot("TC-IMG-13_42_result_ocr")
            api = httpx.get(f"{API}/submissions/{sid}", headers=auth).json()
            order_ok = 0 <= f["verdictAt"] < f["authAt"]
            neutral = f["authColor"] in INFO_RGB and f["authColor"] not in VERDICT_RGB
            ok42 = ok and order_ok and neutral and f["limitationNote"] and f["heatmapShown"] and f["ocrShown"]
            ev = (f"id {sid}: text verdict first={order_ok} (verdict at {f['verdictAt']}, authenticity at {f['authAt']}); authenticity card colour {f['authColor']} "
                  f"(neutral info blue={neutral}); limitation note={f['limitationNote']}; text-image note={f['textImageNote']}; heatmap shown={f['heatmapShown']} "
                  f"{f['heatmapNatural']}; OCR text shown={f['ocrShown']} · {s1}, {s2}, {s3}")
            raw = {"page": f, "api_branch": (api.get("image_submission") or {}).get("analysis_branch")}
            if want("TC-IMG-42"):
                rec("TC-IMG-42", "Pass" if ok42 else "Fail", ev, "text verdict first; neutral authenticity card with note; heatmap over original; OCR text shown", raw)
            if want("TC-IMG-13"):
                merge_screen("TC-IMG-13", ok42, ev, raw)
            if want("TC-IMG-34"):
                merge_screen("TC-IMG-34", f["resnetCaption"],
                             f"caption “Grad-CAM from the detector's ResNet18 model (one of its three models)…” shown={f['resnetCaption']} · {s2}", {"page": f})

        if want("TC-IMG-40"):
            check_screen()
            b.pick_file("Gallery", IMAGES / "img02_urdu_internet.png")
            s_a = b.shot("TC-IMG-40_first_pick")
            xy = b.js("(() => { const e = [...document.querySelectorAll('[aria-label=\"Remove image\"]')].find(x => x.getBoundingClientRect().width); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()")
            for t in ("mousePressed", "mouseReleased"):
                b.send("Input.dispatchMouseEvent", type=t, x=xy[0], y=xy[1], button="left", clickCount=1)
            b.pump(1)
            b.pick_file("Gallery", IMAGES / "photo_landscape.jpg")
            s_b = b.shot("TC-IMG-40_second_pick")
            p0, h0 = len(b.posts), hist()
            b.click("Analyze", wait=0.5)
            ok = b.wait_path("/result/", 180); b.pump(2)
            sid = (b.path() or "").rsplit("/", 1)[-1]
            img = httpx.get(f"{API}/submissions/{sid}/image", headers=auth)
            want_sha = sha((IMAGES / "photo_landscape.jpg").read_bytes())
            first_sha = sha((IMAGES / "img02_urdu_internet.png").read_bytes())
            got = sha(img.content) if img.status_code == 200 else None
            sent, saved = len(b.posts) - p0, hist() - h0
            good = ok and got == want_sha and sent == 1 and saved == 1
            rec("TC-IMG-40", "Pass" if good else "Fail",
                f"picked img02, removed it (×), picked photo_landscape → POSTs {sent}, saved {saved}; stored image = second pick={got == want_sha}, = first pick={got == first_sha} · id {sid} · {s_a}, {s_b}",
                "only the second image is submitted", {"sent": sent, "saved": saved, "stored_sha": got})

        if want("TC-IMG-43"):
            ok, sid = analyse(IMAGES / "photo_landscape.jpg")
            f = page_facts()
            s1 = b.shot("TC-IMG-43_no_text_result")
            b.js("window.scrollBy(0, 700)"); b.pump(0.8)
            s2 = b.shot("TC-IMG-43_no_text_heatmap")
            api = httpx.get(f"{API}/submissions/{sid}", headers=auth).json()
            good = ok and f["noClaim"] and f["authAt"] >= 0 and (f["heatmapShown"] or f["heatmapMissingNote"])
            rec("TC-IMG-43", "Pass" if good and f["uncertainShown"] else ("Finding" if good else "Fail"),
                f"id {sid} (API final {api.get('final_label')}, risk {api.get('combined_risk_score')}): “No readable news text was found in this image, so no news claim was checked.” shown={f['noClaim']}; "
                f"word “Uncertain” on screen={f['uncertainShown']}; authenticity card={f['authAt'] >= 0} ({f['authText']}); heatmap shown={f['heatmapShown']} · {s1}, {s2}",
                "says no text-based verdict; shows Uncertain; authenticity card and heatmap", {"page": f},
                notes="" if f["uncertainShown"] else "The screen says no news claim was checked and shows no verdict card at all; the word “Uncertain” (the stored final label) is not shown.")

        if want("TC-IMG-45"):
            tmp = Path(tempfile.mkdtemp(prefix="img45-"))
            note = tmp / "notes.txt"
            note.write_text("not an image\n", encoding="utf-8")
            msgs, raw = [], {}
            for label, path in (("text file (.txt)", note), ("text renamed .png", IMAGES / "f04_text_renamed.png"),
                                ("PNG over 10 MB", IMAGES / "f22b_just_over_10mb.png")):
                check_screen()
                d0, p0 = len(b.dialogs), len(b.posts)
                b.pick_file("Gallery", path)
                if "Analyze" in b.text():
                    b.click("Analyze", wait=0.5)
                end = time.time() + 60
                while time.time() < end and len(b.dialogs) == d0:
                    b.pump(0.5)
                m = b.dialogs[d0:] or [None]
                raw[label] = {"message": m[0], "request_sent": len(b.posts) - p0}
                msgs.append(f"{label}: “{(m[0] or 'no message').replace(chr(10), ' ')}” (request sent: {len(b.posts) - p0})")
            s = b.shot("TC-IMG-45_last_message")
            all_msgs = all(v["message"] for v in raw.values())
            exact = all("Invalid file type. Please upload a valid image" in (v["message"] or "") for v in raw.values())
            rec("TC-IMG-45", "Pass" if exact else ("Finding" if all_msgs else "Fail"), " · ".join(msgs) + f" · {s}",
                "record the exact message (use case: “Invalid file type. Please upload a valid image”)", raw,
                notes="" if exact else "Each file is refused with a clear message, but the wording differs from the use case's “Invalid file type. Please upload a valid image”.")

        if want("TC-IMG-41"):
            rec("TC-IMG-41", "Not run",
                "HEIC from the iPhone camera roll cannot be produced in a browser; to be tested on the phone. Code: the picker (app/(tabs)/index.tsx) asks expo-image-picker for images with quality 0.85 and no conversion of its own; "
                "the upload is refused in the app unless its type is JPEG, PNG or WEBP (“Choose a JPG, PNG, or WEBP image.”) and the backend accepts only those three (checked from the bytes)",
                "HEIC photo accepted as JPEG", {})

        if want("TC-IMG-44"):
            check_screen()
            b.pick_file("Gallery", IMAGES / "img12_photo_caption.jpg")
            d0 = len(b.dialogs)
            b.click("Analyze", wait=0.4)
            busy = b.analyze_state()
            s1 = b.shot("TC-IMG-44_busy")
            b.pump(2.5)                                   # the request is now being processed by the backend
            pid = (Path(args.run_dir) / "server.pid").read_text().strip()
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
            end = time.time() + 60
            while time.time() < end and len(b.dialogs) == d0:
                b.pump(0.5)
            b.pump(1)
            msg = (b.dialogs[d0:] or [None])[0]
            still = "Analyze" in b.text() and (b.path() or "") in ("/", "")
            s2 = b.shot("TC-IMG-44_backend_stopped")
            good = bool(busy) and busy["ariaDisabled"] == "true" and busy["spinner"] and bool(msg) and still
            rec("TC-IMG-44", "Pass" if good else "Fail",
                f"while waiting: spinner={busy and busy['spinner']}, aria-disabled={busy and busy['ariaDisabled']}; backend killed mid-request → message “{(msg or 'none').replace(chr(10), ' ')}”; no crash, still on Check screen={still} · {s1}, {s2}",
                "spinner + disabled while waiting; clear error and no crash when the backend stops", {"busy": busy, "message": msg, "still": still})
    finally:
        b.close()


if __name__ == "__main__":
    main()
