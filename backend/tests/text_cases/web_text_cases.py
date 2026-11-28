"""Web checks for the text module: TC-TXT-26 (web part) and TC-TXT-35..39, in a real browser.

    python tests/text_cases/web_text_cases.py --web http://localhost:8082 --api http://127.0.0.1:8001 --server-pid-file RUN/server.pid

Headless Microsoft Edge (Chrome DevTools Protocol) at phone size against the Expo web dev server, whose
EXPO_PUBLIC_API_URL is the throwaway backend. Run it from PowerShell (Edge does not start inside the
Bash sandbox). TC-TXT-39 stops the backend (the pid in --server-pid-file), so it runs last.
Screenshots go to screens/; results are merged into results_<date>.json/.csv.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "full_pass"))
sys.path.insert(0, str(HERE))
from ui_pass import PASSWORD, Browser  # noqa: E402
from run_text_cases import INPUTS, save  # noqa: E402

SCREENS = HERE / "screens"
PLACEHOLDER = "Paste a headline or WhatsApp forward in Urdu, Roman Urdu, or English…"


class WebBrowser(Browser):
    def __init__(self, port):
        self.posts: list[str] = []
        super().__init__(port=port)

    def _event(self, msg):
        if msg.get("method") == "Network.requestWillBeSent":
            req = msg["params"]["request"]
            if req["method"] == "POST" and "/submissions/text" in req["url"]:
                self.posts.append(req["url"])
        super()._event(msg)

    def shot(self, name):
        SCREENS.mkdir(exist_ok=True)
        p = SCREENS / f"{name}.png"
        p.write_bytes(base64.b64decode(self.send("Page.captureScreenshot", format="png")["data"]))
        return f"backend/tests/text_cases/screens/{p.name}"

    def press(self, x, y):
        for t in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)

    def button_state(self, x, y):
        # The Analyze Pressable (components/ui/Button.tsx) has role=button and aria-label "Analyze".
        return self.js(f"""(() => {{ const e = [...document.querySelectorAll('[aria-label="Analyze"]')].find(x => x.getBoundingClientRect().width);
            if (!e) return null;
            return {{text: e.innerText.trim(), ariaDisabled: e.getAttribute('aria-disabled'), disabled: !!e.disabled,
                     spinner: !!e.querySelector('[role=progressbar]'), busy: e.getAttribute('aria-busy')}}; }})()""")

    def wait_path(self, prefix, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if (self.path() or "").startswith(prefix):
                return True
            self.pump(0.25)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default="http://localhost:8082")
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--server-pid-file", required=True)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--port", type=int, default=9351)
    ap.add_argument("--only", action="append", default=[], help="TC-TXT-26/35/36/37/38/39 (repeatable)")
    args = ap.parse_args()
    want = lambda cid: not args.only or cid in args.only
    W, API = args.web.rstrip("/"), args.api.rstrip("/") + "/api/v1"

    json_path = HERE / f"results_{args.date}.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    api_ts = (HERE.parents[2] / "lib" / "api.ts").read_text(encoding="utf-8")
    timeout_ms = int(re.search(r"ANALYSIS_TIMEOUT_MS\s*=\s*([\d_]+)", api_ts).group(1).replace("_", ""))

    email = f"txt.web.{int(time.time())}@example.com"
    token = httpx.post(API + "/auth/register", json={"name": "Text web", "email": email, "password": PASSWORD}).json()["access_token"]
    hist = lambda: len(httpx.get(API + "/submissions?skip=0&limit=100", headers={"Authorization": f"Bearer {token}"}).json())

    def rec(cid, result, evidence, expected, raw):
        data["cases"][cid] = {"result": result, "evidence": evidence, "expected": expected, "notes": raw.pop("notes", ""),
                              "raw": raw, "run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "base_url": args.api}
        print(f"{cid:10} {result:16} {evidence}", flush=True)
        save(json_path, data)

    b = WebBrowser(args.port)
    try:
        b.go(W + "/login", 8)
        b.wait_text("Welcome back", 120)
        b.type("you@example.com", email); b.type("Your password", PASSWORD)
        b.click("Sign in", wait=3)
        b.wait_text("Analyze", 60)

        def fresh_check_screen():
            b.go(W + "/", 4)
            b.wait_text("Analyze", 40)

        if want("TC-TXT-36"):
            # TC-TXT-36: empty box
            fresh_check_screen()
            before_text, posts0, h0 = str(b.text()), len(b.posts), hist()
            c = b.center("Analyze")
            state = b.button_state(*c)
            b.press(*c); b.pump(2)
            new_text = [line for line in str(b.text()).splitlines() if line.strip() and line not in before_text.splitlines()]
            shot36 = b.shot("TC-TXT-36_empty_box")
            sent = len(b.posts) - posts0
            msg = (b.dialogs[-1] if b.dialogs else None) or (new_text[0] if new_text else None)
            expected_msg = "Please enter news content before submitting"
            result = "Fail" if sent or hist() != h0 else ("Pass" if msg and expected_msg.lower() in msg.lower() else "Finding")
            rec("TC-TXT-36", result,
                f"Analyze aria-disabled={state and state['ariaDisabled']}; tap → requests sent {sent}, history {h0}→{hist()}; message shown: {json.dumps(msg, ensure_ascii=False)} · {shot36}",
                "message “Please enter news content before submitting”; no request",
                {"button": state, "message": msg, "requests": sent,
                 "notes": "" if result != "Finding" else "No request is sent (Analyze is disabled below 3 characters), but no message is shown; the use case text “Please enter news content before submitting” does not appear."})

        if want("TC-TXT-26"):
            # TC-TXT-26: <script> text on result and history screens
            fresh_check_screen()
            text26 = INPUTS["TC-TXT-26"]
            d0 = len(b.dialogs)
            b.type(PLACEHOLDER, text26, tag="textarea")
            b.click("Analyze", wait=1)
            ok_route = b.wait_path("/result/", 120)
            b.pump(2)
            result_plain = "<script>alert(1)</script>" in b.text()
            injected = b.js("[...document.querySelectorAll('script')].some(s => s.textContent.includes('alert(1)'))")
            s1 = b.shot("TC-TXT-26_result")
            b.go(W + "/", 4); b.wait_text("Analyze", 60)
            b.click("History", wait=2)                    # open History in the app, as a user would
            end = time.time() + 30
            while time.time() < end and "<script>alert(1)</script>" not in b.text():
                b.pump(0.5)
            hist_plain = "<script>alert(1)</script>" in b.text()
            s2 = b.shot("TC-TXT-26_history")
            alerts = b.dialogs[d0:]
            web_ok = ok_route and result_plain and hist_plain and not injected and not alerts
            web = {"ok": web_ok, "evidence": f"result shows the text literally={result_plain}, history={hist_plain}, alert fired={bool(alerts)}, <script> element injected={injected} · {s1}, {s2}",
                   "dialogs": alerts}
            case = data["cases"].get("TC-TXT-26")
            if case:
                case["raw"]["web"] = web
                api_ok = case["raw"].get("stored_equals_sent") and (case["raw"].get("facts") or {}).get("status") == 201
                case["result"] = "Pass" if api_ok and web_ok else "Fail"
                case["evidence"] = re.sub(r" · web.*$", "", case["evidence"]) + " · web: " + web["evidence"]
                save(json_path, data)
                print(f"TC-TXT-26  {case['result']:16} {case['evidence']}")

        if want("TC-TXT-35"):
            # TC-TXT-35: double tap Analyze
            fresh_check_screen()
            b.type(PLACEHOLDER, INPUTS["TC-TXT-07"], tag="textarea")
            h0, p0 = hist(), len(b.posts)
            c = b.center("Analyze")
            b.press(*c); b.press(*c)
            b.pump(0.3)
            busy = b.button_state(*c)
            s35a = b.shot("TC-TXT-35_busy")
            b.wait_path("/result/", 120); b.pump(1.5)
            h1, sent = hist(), len(b.posts) - p0
            ok = h1 - h0 == 1 and sent == 1 and busy and (busy["ariaDisabled"] == "true" or busy["disabled"]) and busy["spinner"]
            rec("TC-TXT-35", "Pass" if ok else "Fail",
                f"two taps 0 ms apart → POSTs {sent}, saved {h1 - h0}; while busy: spinner={busy and busy['spinner']}, aria-disabled={busy and busy['ariaDisabled']} · {s35a}",
                "spinner; disabled while busy; one submission", {"busy_state": busy, "posts": sent, "saved": h1 - h0})

        if want("TC-TXT-37"):
            # TC-TXT-37: long Urdu result reads right to left
            fresh_check_screen()
            art = INPUTS["TC-TXT-03"]
            b.type(PLACEHOLDER, art, tag="textarea")
            b.click("Analyze", wait=1)
            b.wait_path("/result/", 120); b.pump(2.5)
            style = b.js(f"""(() => {{ const want = {json.dumps(art[:40])};
                const els = [...document.querySelectorAll('div,span')].filter(e => e.innerText && e.innerText.startsWith(want));
                if (!els.length) return null; const e = els[els.length - 1]; const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
                return {{direction: cs.direction, textAlign: cs.textAlign, fontFamily: cs.fontFamily, writingDirection: e.dir || cs.unicodeBidi,
                         width: r.width, viewport: innerWidth, height: r.height, lineHeight: parseFloat(cs.lineHeight) || null,
                         overflowX: e.scrollWidth > e.clientWidth + 1}}; }})()""")
            s37 = b.shot("TC-TXT-37_long_urdu_result")
            b.js("window.scrollBy(0, 500)"); b.pump(0.5)
            s37b = b.shot("TC-TXT-37_long_urdu_result_scrolled")
            rtl = bool(style) and style["direction"] == "rtl" and style["textAlign"] in ("right", "start")
            wraps = bool(style) and style["width"] <= style["viewport"] and not style["overflowX"] and (not style["lineHeight"] or style["height"] > 2 * style["lineHeight"])
            urdu_font = bool(style) and "NotoNastaliqUrdu" in style["fontFamily"]   # fonts.urdu in constants/theme.ts
            rec("TC-TXT-37", "Pass" if rtl and wraps and urdu_font else "Fail",
                (f"direction {style['direction']}, text-align {style['textAlign']}, font {style['fontFamily'][:60]}, width {style['width']:.0f}/{style['viewport']} px, "
                 f"{(style['height'] / style['lineHeight']) if style['lineHeight'] else 0:.0f} lines, overflow={style['overflowX']} · {s37}, {s37b}") if style else f"article text not found on the result screen · {s37}",
                "RTL, correct font, wrapping", {"style": style})

        if want("TC-TXT-38"):
            # TC-TXT-38: Roman Urdu request completes; the app's timeout
            fresh_check_screen()
            b.type(PLACEHOLDER, INPUTS["TC-TXT-04"], tag="textarea")
            t0 = time.time()
            b.click("Analyze", wait=0.5)
            done = b.wait_path("/result/", timeout_ms / 1000 + 10)
            took = time.time() - t0
            b.pump(1.5)
            s38 = b.shot("TC-TXT-38_roman_urdu_result")
            rec("TC-TXT-38", "Pass" if done and took < timeout_ms / 1000 else "Fail",
                f"result opened after {took:.1f} s (click to result screen); app analysis timeout ANALYSIS_TIMEOUT_MS = {timeout_ms} ms ({timeout_ms // 1000} s, lib/api.ts) · {s38}",
                "completes without timing out; report app timeout", {"seconds": round(took, 1), "timeout_ms": timeout_ms})

        if want("TC-TXT-39"):
            # TC-TXT-39: backend stopped
            fresh_check_screen()
            b.type(PLACEHOLDER, INPUTS["TC-TXT-02"], tag="textarea")
            pid = Path(args.server_pid_file).read_text().strip()
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
            for _ in range(20):
                try:
                    httpx.get(args.api.rstrip("/") + "/health", timeout=1)
                    time.sleep(0.5)
                except httpx.HTTPError:
                    break
            d0 = len(b.dialogs)
            b.click("Analyze", wait=1)
            end = time.time() + 30
            while time.time() < end and len(b.dialogs) == d0 and "Cannot reach the backend" not in b.text():
                b.pump(0.5)
            b.pump(1)
            shown = (b.dialogs[d0:] or [None])[0] or ("Cannot reach the backend" if "Cannot reach the backend" in b.text() else None)
            still = "Analyze" in b.text() and (b.path() or "") in ("/", "")
            kept = b.js(f"(() => {{ const t = [...document.querySelectorAll('textarea')].find(x => x.placeholder === {json.dumps(PLACEHOLDER)}); return t ? t.value.length : -1; }})()")
            s39 = b.shot("TC-TXT-39_backend_stopped")
            ok = bool(shown) and "Cannot reach the backend at" in shown and still
            rec("TC-TXT-39", "Pass" if ok else "Fail",
                f"message: {json.dumps(shown, ensure_ascii=False)}; no crash, still on the Check screen={still}, typed text kept ({kept} chars) · {s39}",
                "“Cannot reach the backend at …”; no crash", {"message": shown, "still_usable": still})
    finally:
        b.close()


if __name__ == "__main__":
    main()
