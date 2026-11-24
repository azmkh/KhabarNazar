"""Web UI and navigation cases (TC-UI, TC-NAV) in a real browser.

    python tests/full_pass/ui_pass.py --web http://localhost:8082 --api http://127.0.0.1:8001 --db sqlite:RUN/test.db --run-dir RUN

Drives headless Microsoft Edge through the Chrome DevTools Protocol at phone size (390x844, touch),
against the Expo web dev server (EXPO_PUBLIC_API_URL = the throwaway backend). Clicks are real mouse
events at element centres, typing is real text input, image picking goes through the browser's file
chooser. Every case saves a screenshot in tests/full_pass/screenshots/. Run it from PowerShell
(Edge does not start inside the Bash tool's sandbox). Results: RUN/results_ui.json.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from websockets.sync.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_common import BACKEND, HERE, PY, TEST_JWT_SECRET, resolve_db  # noqa: E402

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SHOTS = HERE / "screenshots"
PASSWORD = "Password123!"


class CI(str):
    """Page text compared case-insensitively (the app shows card titles in capitals via CSS)."""
    def __contains__(self, x):
        return str(x).lower() in self.lower()

    def find(self, x, *a):
        return self.lower().find(str(x).lower(), *a)


class Browser:
    def __init__(self, port=9333):
        self.tmp = tempfile.mkdtemp(prefix="fp-edge-")
        self.proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={self.tmp}",
                                      "--no-first-run", "--disable-gpu", "--window-size=390,844", "about:blank"])
        for _ in range(60):
            try:
                pages = httpx.get(f"http://127.0.0.1:{port}/json").json()
                page = next(p for p in pages if p["type"] == "page")
                break
            except Exception:
                time.sleep(0.5)
        self.ws = connect(page["webSocketDebuggerUrl"], max_size=50_000_000, open_timeout=20)
        self.n = 0
        self.dialogs: list[str] = []
        self.chooser = None
        self.send("Page.enable"); self.send("Runtime.enable"); self.send("Network.enable")
        self.send("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        self.send("Page.setInterceptFileChooserDialog", enabled=True)

    def _event(self, msg):
        if msg.get("method") == "Page.javascriptDialogOpening":
            self.dialogs.append(msg["params"]["message"])
            self._send_raw("Page.handleJavaScriptDialog", accept=True)
        elif msg.get("method") == "Page.fileChooserOpened":
            self.chooser = msg["params"]

    def _send_raw(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        return self.n

    def send(self, method, **params):
        mid = self._send_raw(method, **params)
        while True:
            msg = json.loads(self.ws.recv(timeout=120))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self._event(msg)

    def pump(self, seconds=0.3):
        end = time.time() + seconds
        while time.time() < end:
            try:
                self._event(json.loads(self.ws.recv(timeout=max(0.01, end - time.time()))))
            except TimeoutError:
                break

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def go(self, url, wait=6):
        self.send("Page.navigate", url=url)
        self.pump(wait)

    def text(self):
        return CI(self.js("document.body ? document.body.innerText : ''") or "")

    def path(self):
        return self.js("location.pathname")

    def wait_text(self, needle, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            if needle in self.text():
                return True
            self.pump(0.5)
        return False

    def wait_any(self, needles, timeout=240):
        end = time.time() + timeout
        while time.time() < end:
            t = self.text()
            for n in needles:
                if n in t:
                    return n
            self.pump(1)
        return None

    def center(self, label, exact=True):
        return self.js(f"""(() => {{
            const want = {json.dumps(label)};
            const els = [...document.querySelectorAll('body *')].filter(e => {{
              const r = e.getBoundingClientRect(); if (!r.width || !r.height) return false;
              const t = (e.innerText || e.getAttribute('aria-label') || '').trim();
              return {'t.toLowerCase() === want.toLowerCase()' if exact else 't.toLowerCase().includes(want.toLowerCase())'};
            }});
            if (!els.length) return null;
            const e = els[els.length - 1]; e.scrollIntoView({{block: 'center'}});
            const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2];
        }})()""")

    def click(self, label, exact=True, wait=1.0):
        c = self.center(label, exact)
        if not c:
            raise RuntimeError(f"no element with text {label!r}")
        for t in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=t, x=c[0], y=c[1], button="left", clickCount=1)
        self.pump(wait)

    def type(self, placeholder, value, tag="input,textarea"):
        ok = self.js(f"""(() => {{ const e = [...document.querySelectorAll({json.dumps(tag)})].find(x => x.placeholder === {json.dumps(placeholder)} && x.getBoundingClientRect().width);
            if (!e) return false; e.scrollIntoView({{block:'center'}}); e.focus(); e.select && e.select(); return true; }})()""")
        if not ok:
            raise RuntimeError(f"no input with placeholder {placeholder!r}")
        self.send("Input.insertText", text=value)
        self.pump(0.4)

    def shot(self, name):
        SHOTS.mkdir(exist_ok=True)
        data = self.send("Page.captureScreenshot", format="png")["data"]
        p = SHOTS / f"{name}.png"
        p.write_bytes(base64.b64decode(data))
        return f"backend/tests/full_pass/screenshots/{p.name}"

    def pick_file(self, button, file):
        self.chooser = None
        self.click(button, wait=1.5)
        if not self.chooser:
            self.pump(2)
        if not self.chooser:
            raise RuntimeError("no file chooser opened")
        self.send("DOM.setFileInputFiles", files=[str(file)], backendNodeId=self.chooser["backendNodeId"])
        self.pump(2)

    def close(self):
        try:
            self.ws.close()
        finally:
            self.proc.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default="http://localhost:8082")
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run = Path(args.run_dir).resolve()
    out = run / "results_ui.json"
    results: list[dict] = []
    api = httpx.Client(base_url=args.api + "/api/v1", timeout=240)
    tag = datetime.now().strftime("%H%M%S")

    def rec(id_, title, input_, expected, actual, evidence, result, uc=None):
        results.append({"id": id_, "title": title, "input": input_, "expected": expected, "actual": actual, "evidence": evidence,
                        "result": result, "how": "Real (browser)", "group": id_.split("-")[1], "use_case": uc, "db": "ui",
                        "time": datetime.now().isoformat(timespec="seconds")})
        print(f"[{result:16}] {id_:10} {title[:80]}", flush=True)
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    def account(key, admin=False):
        email = f"ui.{key}.{tag}@example.com"
        api.post("/auth/register", json={"name": f"UI {key}", "email": email, "password": PASSWORD})
        if admin:
            env = {**os.environ, "DATABASE_URL": resolve_db(args.db), "JWT_SECRET": TEST_JWT_SECRET, "PYTHONUTF8": "1"}
            env = {k: v for k, v in env.items() if not k.startswith("KHABARNAZAR_")}
            subprocess.run([str(PY), "scripts/set_user_role.py", email, "admin"], cwd=BACKEND, env=env, check=True, capture_output=True)
        return email

    def guarded(id_, title, uc, fn):
        try:
            fn()
        except Exception as exc:
            name = f"{id_}_error"
            try:
                ev = b.shot(name)
            except Exception:
                ev = "no screenshot"
            rec(id_, title, "-", "-", f"could not complete: {exc}", ev, "Blocked", uc)

    user, admin, fresh = account("user"), account("admin", admin=True), account("fresh")
    b = Browser()
    W = args.web

    def login(email):
        b.go(W + "/login", 8)
        b.wait_text("Welcome back", 40)
        b.type("you@example.com", email)
        b.type("Your password", PASSWORD)
        b.click("Sign in", wait=4)
        b.wait_text("Analyze", 30)

    def logout_storage():
        b.js("localStorage.clear()")

    # TC-UI-01 splash / boot
    def ui01():
        b.go(W + "/", 0.6)
        early = b.text()
        p1 = b.shot("UI-01_boot")
        for _ in range(30):
            if b.path() == "/login":
                break
            b.pump(1)
        rec("TC-UI-01", "Splash / boot screen, then the sign-in page when signed out", "open / signed out",
            "boot screen with the wordmark, then /login", f"early text {early[:60]!r}; now at {b.path()}", p1,
            "Pass" if b.path() == "/login" else "Fail", "UC-2 Login")
    guarded("TC-UI-01", "Splash", "UC-2 Login", ui01)

    def ui02():
        b.go(W + "/login", 6)
        b.type("you@example.com", user)
        b.type("Your password", "WrongPassword1")
        n = len(b.dialogs)
        b.click("Sign in", wait=1)
        msg = "Incorrect email or password entered"
        for _ in range(20):
            if msg in b.text() or len(b.dialogs) > n:
                break
            b.pump(0.5)
        t = b.text()
        ev = b.shot("UI-02_login_error")
        rec("TC-UI-02", "Login screen shows the wrong-password message", f"{user} / wrong password", f"'{msg}' on screen",
            f"on screen: {msg in t}; dialogs after the click {b.dialogs[n:]}", ev, "Pass" if msg in t or any(msg.lower() in d.lower() for d in b.dialogs[n:]) else "Fail", "UC-2 Login")
    guarded("TC-UI-02", "Login error", "UC-2 Login", ui02)

    def ui03():
        logout_storage()
        b.go(W + "/register", 6)
        email = f"ui.reg.{tag}@example.com"
        b.type("Your name (optional)", "Register Via UI")
        b.type("you@example.com", email)
        b.type("At least 6 characters", PASSWORD)
        b.type("Repeat password", PASSWORD + "x")
        n = len(b.dialogs)
        b.click("Create account", wait=2)
        mismatch = CI(b.text() + " ".join(b.dialogs[n:]))
        ev1 = b.shot("UI-03a_register_mismatch")
        b.type("Repeat password", PASSWORD)
        b.click("Create account", wait=6)
        where = b.path()
        ev2 = b.shot("UI-03b_after_register")
        rec("TC-UI-03", "Register: mismatch message, then where the app goes (TC-REG-10)", "name, new email, password; first a wrong confirmation",
            "a mismatch message; after registering: signed in (home) or the login page",
            f"mismatch message shown: {'match' in mismatch.lower()}; after registering at {where!r} (home 'Analyze' visible: {'Analyze' in b.text()})",
            f"{ev1}; {ev2}", "Pass" if where in ("/", "/(tabs)") or "Analyze" in b.text() else "Fail", "UC-1 User Registration")
    guarded("TC-UI-03", "Register", "UC-1 User Registration", ui03)

    def ui04():
        logout_storage()
        b.go(W + "/forgot", 6)
        b.wait_text("Reset password", 20)
        b.type("you@example.com", user)
        n = len(b.dialogs)
        b.click("Continue", wait=2)
        t = CI(b.text() + " " + " ".join(b.dialogs[n:]))
        ev = b.shot("UI-04_forgot")
        rec("TC-UI-04", "Forgot password shows 'not available'", "open /forgot", "message that reset is not available",
            f"'not available' shown: {'not available' in t}", ev, "Known-limitation" if "not available" in t else "Fail", "UC-2 Login")
    guarded("TC-UI-04", "Forgot", "UC-2 Login", ui04)

    state = {}

    def ui05():
        login(user)
        ev0 = b.shot("UI-05a_home")
        disabled = b.js("""(() => { let e=[...document.querySelectorAll('body *')].filter(x=>x.innerText && x.innerText.trim().toLowerCase().endsWith('analyze') && x.getBoundingClientRect().width).pop();
            while (e && !e.hasAttribute('aria-disabled')) e = e.parentElement; return e ? e.getAttribute('aria-disabled') : 'not found'; })()""")
        n = len(b.dialogs)
        b.click("Analyze", wait=2)
        t = b.text()
        ev1 = b.shot("UI-05b_empty_submit")
        msgs = b.dialogs[n:]
        rec("TC-UI-05", "Home/check: submitting nothing", "press Analyze with an empty box", "submission blocked (use case wording: 'Please enter news content before submitting')",
            f"Analyze aria-disabled={disabled!r} (button greyed out, counter 0 / 10,000); no message shown; dialogs {msgs}; still on {b.path()}", f"{ev0}; {ev1}",
            "Pass" if b.path() == "/" and (str(disabled) == "true" or msgs) else "Fail", "UC-3 Submit Text")
    guarded("TC-UI-05", "Empty submit", "UC-3 Submit Text", ui05)

    def ui06():
        urdu = "حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔"
        b.go(W + "/", 6)
        b.type("Paste a headline or WhatsApp forward in Urdu, Roman Urdu, or English…", urdu)
        rtl = b.js("""(() => { const e=document.querySelector('textarea'); const s=getComputedStyle(e); return {direction:s.direction, align:s.textAlign, font:s.fontFamily}; })()""")
        b.click("Analyze", wait=0.6)
        busy = b.shot("UI-06a_analyzing")
        busy_text = b.text()
        got = b.wait_any(["Why this result", "Could not"], 240)
        b.pump(1)
        state["text_result"] = b.path()
        t = b.text()
        ev = b.shot("UI-06b_urdu_result")
        overflow = b.js("document.documentElement.scrollWidth > window.innerWidth")
        urdu_dir = b.js(f"""(() => {{ const e=[...document.querySelectorAll('div,span')].filter(x=>x.innerText && x.innerText.trim()==={json.dumps(urdu)}).pop(); if(!e) return null; const s=getComputedStyle(e); return {{direction:s.direction, align:s.textAlign, font:s.fontFamily, writing:e.getAttribute('dir')}}; }})()""")
        ok = got == "Why this result" and not overflow
        rec("TC-UI-06", "Urdu text check: loading state, result, explanation, right-to-left text", "U02 (internet shutdown sentence)",
            "spinner/busy while analysing; result with verdict, score and 'Why this result'; Urdu shown right-to-left; no sideways scroll",
            f"while busy: {'Analyzing' in busy_text or 'Checking' in busy_text or 'analys' in busy_text.lower()}; result at {state['text_result']}; "
            f"input style {rtl}; result text style {urdu_dir}; horizontal overflow {overflow}", f"{busy}; {ev}", "Pass" if ok else "Fail", "UC-3 Submit Text")
        rec("TC-UI-07", "Explanation panel shows highlighted words and the plain-language summary", "same result", "'Why this result' card with words and summary",
            f"card present {'Why this result' in t}; mentions 'AI estimate' {'AI estimate' in t}", ev, "Pass" if "Why this result" in t else "Fail", "UC-5 View Explainability Panel")
    guarded("TC-UI-06", "Urdu text", "UC-3 Submit Text", ui06)

    def ui08():
        b.go(W + "/", 6)
        b.type("Paste a headline or WhatsApp forward in Urdu, Roman Urdu, or English…", "Hukoomat ne elan kiya hai ke mulk bhar mein saat din ke liye internet service band kar di jayegi.")
        b.click("Analyze", wait=1)
        got = b.wait_any(["Why this result", "Could not"], 240)
        ev = b.shot("UI-08_roman_result")
        rec("TC-UI-08", "Roman Urdu text check end to end", "R02", "result screen with verdict and explanation", f"reached: {got}; at {b.path()}",
            ev, "Pass" if got == "Why this result" else "Fail", "UC-3 Submit Text")
        b.go(W + "/", 6)
        b.type("Paste a headline or WhatsApp forward in Urdu, Roman Urdu, or English…", "The city council said that the new bus route will start operating from next Monday morning.")
        b.click("Analyze", wait=1)
        b.wait_any(["Why this result", "Could not"], 240)
        t = b.text()
        ev = b.shot("UI-09_english_result")
        rec("TC-UI-09", "English text: lower-reliability note on screen", "E03", "the result says English results are less reliable",
            f"note shown: {'less reliable' in t}", ev, "Known-limitation" if "less reliable" in t else "Fail", "UC-3 Submit Text")
    guarded("TC-UI-08", "Roman/English", "UC-3 Submit Text", ui08)

    def ui10():
        b.go(W + "/", 6)
        b.click("Image", wait=1)
        b.pick_file("Gallery", HERE / "images" / "roman_headline.png")
        ev0 = b.shot("UI-10a_image_picked")
        changed = False
        try:
            b.pick_file("Gallery", HERE / "images" / "urdu_headline.png")
            changed = True
        except Exception:
            pass
        ev1 = b.shot("UI-10b_image_changed")
        b.click("Analyze", wait=1)
        got = b.wait_any(["Image authenticity", "Could not"], 300)
        b.pump(4)
        t = b.text()
        state["image_result"] = b.path()
        evs = [b.shot("UI-10c_image_result_top")]
        b.js("window.scrollTo(0, document.body.scrollHeight/2)"); b.pump(1); evs.append(b.shot("UI-10d_image_result_middle"))
        b.js("window.scrollTo(0, document.body.scrollHeight)"); b.pump(1); evs.append(b.shot("UI-10e_image_result_bottom"))
        i_auth = t.find("Image authenticity")
        verdict_first = "separate from the verdict above" in t
        caption = "ResNet18" in t
        heat = b.js("[...document.querySelectorAll('img')].filter(i=>i.naturalWidth>0).length")
        ok = got == "Image authenticity" and verdict_first and caption
        rec("TC-UI-10", "Image with text: pick, change, analyse; news verdict first, authenticity separate, Grad-CAM caption", "roman_headline.png, changed to urdu_headline.png",
            "verdict card first; 'Image authenticity (separate from the verdict above)'; caption names ResNet18; images load",
            f"changed picture: {changed}; reached {got}; authenticity heading at char {i_auth}; separate-heading {verdict_first}; ResNet18 caption {caption}; loaded <img> {heat}",
            "; ".join([ev0, ev1] + evs), "Pass" if ok else "Fail", "UC-4 Submit Image")
    guarded("TC-UI-10", "Image with text", "UC-4 Submit Image", ui10)

    def ui11():
        b.go(W + "/", 6)
        b.click("Image", wait=1)
        b.pick_file("Gallery", HERE / "images" / "local_fox_no_text.jpg")
        b.click("Analyze", wait=1)
        got = b.wait_any(["Image authenticity", "Could not"], 300)
        b.pump(3)
        t = b.text()
        ev = b.shot("UI-11_image_no_text")
        b.js("window.scrollTo(0, document.body.scrollHeight)"); b.pump(1)
        ev2 = b.shot("UI-11b_image_no_text_bottom")
        ok = got and "No news claim" in t or "no news claim" in t.lower()
        rec("TC-UI-11", "Image without text: no verdict invented, authenticity shown", "local_fox_no_text.jpg", "no fake-news verdict ('No news claim was checked'); authenticity + heatmap",
            f"reached {got}; 'no news claim' {('no news claim' in t.lower())}; heading 'Image authenticity' {('Image authenticity' in t)}", f"{ev}; {ev2}",
            "Pass" if ok else "Fail", "UC-4 Submit Image")
    guarded("TC-UI-11", "Image no text", "UC-4 Submit Image", ui11)

    def ui12():
        b.go(W + "/history", 8)
        b.wait_text("History", 20)
        t = b.text()
        ev = b.shot("UI-12a_history")
        logout_storage()
        login(fresh)
        b.go(W + "/history", 8)
        t2 = b.text()
        ev2 = b.shot("UI-12b_history_empty")
        rec("TC-UI-12", "History list and its empty state", "user with checks; new user", "items listed; empty state for a new user ('You have not submitted any content yet')",
            f"items show the Urdu check: {'حکومت' in t}; empty state text: {t2[:160]!r}", f"{ev}; {ev2}",
            "Pass" if "حکومت" in t and ("No checks" in t2 or "first analysis" in t2) else "Fail", "UC-7 View Submission History")
    guarded("TC-UI-12", "History", "UC-7 View Submission History", ui12)

    def ui13():
        logout_storage()
        login(user)
        b.go(W + state["text_result"], 8)
        b.wait_text("Why this result", 30)
        b.click("Dispute this result", wait=3)
        b.wait_text("Why do you disagree?", 20)
        b.type("e.g. The official press release on the ministry website says the opposite…", "short")
        t_short = b.text()
        ev1 = b.shot("UI-13a_dispute_short")
        b.type("e.g. The official press release on the ministry website says the opposite…", "The ministry denied this; the service stays on.")
        b.type("e.g. geo.tv/news/12345", "geo.tv/news/12345")
        b.click("Submit dispute", wait=4)
        t = b.text()
        ev2 = b.shot("UI-13b_dispute_submitted")
        state["dispute_dialogs"] = b.dialogs[-2:]
        b.go(W + state["text_result"], 8)
        t3 = b.text()
        ev3 = b.shot("UI-13c_result_pending")
        rec("TC-UI-13", "Dispute: short-justification message, submit, then 'waiting for review'", "justification 'short', then a full one + 'geo.tv/news/12345'",
            "'Please write at least 10 characters'; submitted; result shows the dispute as pending",
            f"minimum-length hint {('characters minimum' in t_short) or ('at least' in t_short)} ('5 / 10 characters minimum'; use case wording 'Please provide a justification…' not used); dialogs {state['dispute_dialogs']}; result mentions pending/review: {'ending' in t3 or 'review' in t3.lower()}",
            f"{ev1}; {ev2}; {ev3}", "Pass" if (("characters minimum" in t_short) or ("at least" in t_short)) and ("ending" in t3 or "review" in t3.lower()) else "Fail", "UC-6 Dispute AI Prediction")
    guarded("TC-UI-13", "Dispute", "UC-6 Dispute AI Prediction", ui13)

    def ui14():
        b.go(W + "/profile", 6)
        ev1 = b.shot("UI-14a_profile")
        b.click("My profile", wait=3)
        ev2 = b.shot("UI-14b_my_profile")
        b.go(W + "/profile/edit", 6)
        ev3 = b.shot("UI-14c_edit_profile")
        t = b.text()
        rec("TC-UI-14", "Profile, my profile, edit profile", "open each", "screens render; edit offers a photo only (no API for profile editing)",
            f"edit screen offers photo: {'Choose photo' in t}", f"{ev1}; {ev2}; {ev3}", "Pass" if "Choose photo" in t else "Fail", "Profile")
    guarded("TC-UI-14", "Profile", "Profile", ui14)

    def ui15():
        b.go(W + "/profile/logout", 6)
        before = b.js("localStorage.getItem('kn_access_token') !== null")
        b.click("Sign out", wait=4)
        after = b.js("localStorage.getItem('kn_access_token')")
        ev = b.shot("UI-15_after_logout")
        rec("TC-UI-15", "Logout clears the stored token on web (TC-LOG-13)", "Profile > Sign out", "kn_access_token removed; back at /login",
            f"token before {before}; after {after!r}; at {b.path()}", ev, "Pass" if before and after is None and b.path() == "/login" else "Fail", "UC-2 Login")
    guarded("TC-UI-15", "Logout", "UC-2 Login", ui15)

    def ui16():
        login(admin)
        b.go(W + "/admin", 8)
        ev1 = b.shot("UI-16a_admin_dashboard")
        b.go(W + "/admin/disputes", 8)
        t = b.text()
        ev2 = b.shot("UI-16b_admin_disputes")
        disputes = httpx.get(args.api + "/api/v1/disputes?status=pending&limit=100",
                             headers={"Authorization": "Bearer " + httpx.post(args.api + "/api/v1/auth/login", json={"email": admin, "password": PASSWORD}).json()["access_token"]}).json()
        mine = [d for d in disputes if "ministry denied" in (d.get("justification") or "")]
        did = mine[0]["id"] if mine else None
        b.go(W + f"/admin/review/{did}", 8)
        b.wait_text("Your decision", 20)
        ev3 = b.shot("UI-16c_admin_review")
        b.click("Override verdict", exact=False, wait=2)
        n = len(b.dialogs)
        b.pump(1)
        no_comment = b.dialogs[n - 1:] if len(b.dialogs) >= n else []
        ev4 = b.shot("UI-16d_admin_no_comment")
        b.type("Explain your decision for the audit trail…", "Checked with the ministry; overriding to Real.")
        b.click("Credible", wait=1)
        b.click("Override verdict", exact=False, wait=4)
        ev5 = b.shot("UI-16e_admin_saved")
        saved = b.dialogs[-2:]
        b.go(W + "/admin/submissions", 8)
        ev6 = b.shot("UI-16f_admin_submissions")
        b.go(W + "/moderation", 8)
        ev7 = b.shot("UI-16g_moderation_tab")
        rec("TC-UI-16", "Admin: dashboard, queue, review (comment required), override, all submissions, moderation tab", f"dispute {did} from TC-UI-13",
            "each screen renders; no comment -> 'A comment is required'; override saved", f"queue lists the dispute: {'ministry' in t or bool(mine)}; "
            f"no-comment dialog {no_comment}; dialogs after save {saved}", "; ".join([ev1, ev2, ev3, ev4, ev5, ev6, ev7]),
            "Pass" if any("comment is required" in d for d in b.dialogs) and any("recorded" in d for d in b.dialogs) else "Fail", "UC-8 Admin Reviews Dispute")
        logout_storage()
        login(user)
        b.go(W + state["text_result"], 8)
        b.pump(2)
        t = b.text()
        ev = b.shot("UI-17_user_sees_override")
        rec("TC-UI-17", "The user's result shows the admin's label and comment", "the disputed result after the override",
            "final label from the admin, marked as such, with the comment", f"comment shown {'overriding to Real' in t}; mentions admin {'dmin' in t}",
            ev, "Pass" if "overriding to Real" in t else "Fail", "UC-8 Admin Reviews Dispute")
    guarded("TC-UI-16", "Admin", "UC-8 Admin Reviews Dispute", ui16)

    def ui18():
        b.send("Network.setBlockedURLs", urls=["*127.0.0.1:8001*"])
        b.go(W + "/", 6)
        b.type("Paste a headline or WhatsApp forward in Urdu, Roman Urdu, or English…", "حکومت نے آج نئی سڑک کا افتتاح کیا ہے")
        b.click("Analyze", wait=5)
        t = b.text()
        ev = b.shot("UI-18_backend_unreachable")
        d = b.dialogs[-1:]
        b.send("Network.setBlockedURLs", urls=[])
        msg = any("Cannot reach the backend" in x for x in d) or "Cannot reach the backend" in t
        rec("TC-UI-18", "Backend unreachable message (TC-APP-04)", "requests to the API blocked in the browser", "'Cannot reach the backend at …'",
            f"dialog {d}", ev, "Pass" if msg else "Fail", "App-backend")
    guarded("TC-UI-18", "Unreachable", "App-backend", ui18)

    def nav():
        logout_storage()
        b.go(W + "/login", 6)
        res = {}
        for p in ("/history", "/result/1", "/dispute/1", "/admin", "/profile"):
            b.go(W + p, 7)
            res[p] = b.path()
        b.go(W + "/register", 6)
        res["/register"] = b.path()
        ev = b.shot("NAV-01_signed_out_deeplink")
        ok = all(v == "/login" for k, v in res.items() if k != "/register") and res["/register"] == "/register"
        rec("TC-NAV-01", "Signed out: deep links go to /login; /register stays open", ", ".join(res), "/login for all; /register stays",
            json.dumps(res), ev, "Pass" if ok else "Fail", "Navigation")
        login(user)
        b.go(W + "/history", 8)
        b.send("Page.reload"); b.pump(9)
        ev = b.shot("NAV-02_reload_keeps_place")
        rec("TC-NAV-02", "Valid session: reload keeps the user where they are", "reload on /history", "still /history", b.path(), ev,
            "Pass" if b.path() == "/history" else "Fail", "Navigation")
        b.js("localStorage.setItem('kn_access_token', 'corrupt.token.value')")
        b.go(W + "/history", 9)
        p_corrupt = b.path()
        ev1 = b.shot("NAV-03a_corrupt_token")
        uid = httpx.post(args.api + "/api/v1/auth/login", json={"email": user, "password": PASSWORD}).json()["user"]["id"]
        expired = jwt.encode({"sub": str(uid), "role": "user", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)}, TEST_JWT_SECRET, algorithm="HS256")
        login(user)
        b.js(f"localStorage.setItem('kn_access_token', {json.dumps(expired)})")
        b.go(W + "/history", 9)
        p_expired = b.path()
        ev2 = b.shot("NAV-03b_expired_token")
        rec("TC-NAV-03", "Corrupt or expired token at start-up goes to /login", "corrupt token; token expired 5 min ago; open /history",
            "/login both times", f"corrupt -> {p_corrupt}; expired -> {p_expired}", f"{ev1}; {ev2}",
            "Pass" if p_corrupt == p_expired == "/login" else "Fail", "Navigation")
        login(user)
        b.go(W + "/admin", 8)
        ev = b.shot("NAV-04_non_admin_admin")
        rec("TC-NAV-04", "A non-admin opening /admin goes to the home tab", "user opens /admin", "redirected to /", b.path(), ev,
            "Pass" if b.path() == "/" else "Fail", "Navigation")
    guarded("TC-NAV-01", "Navigation", "Navigation", nav)

    b.close()
    print("done", out)


if __name__ == "__main__":
    main()
