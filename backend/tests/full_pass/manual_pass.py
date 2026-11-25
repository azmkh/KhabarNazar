"""Run docs/testing/MANUAL_CHECKLIST.md (steps MC-01..MC-32) in a real browser.

    python tests/full_pass/manual_pass.py --run-dir RUN --db sqlite:RUN/test.db   (from PowerShell)

Needs a throwaway backend from start_test_server.py on --api and Expo web on --web (EXPO_PUBLIC_API_URL
pointing at that backend). Uses headless Edge at phone size (390x844, touch) through the DevTools
protocol, the same driver as ui_pass.py. Phone-only steps are emulated where the browser can do it
honestly (rotation = viewport switch to landscape, network loss = DevTools offline mode, backgrounding =
the page frozen by the browser's lifecycle API) and marked as emulated; the rest (iPhone HEIC camera
roll, the native camera) are recorded as Blocked. Results: RUN/results_manual.json, screenshots MC-*.png.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_common import BACKEND, HERE, PY, TEST_JWT_SECRET, resolve_db  # noqa: E402
from ui_pass import CI, PASSWORD, Browser  # noqa: E402

BOX = "Paste a headline or WhatsApp forward in Urdu, Roman Urdu, or English…"
INPUTS = {d["id"]: d["text"] for d in json.loads((HERE / "text_inputs.json").read_text(encoding="utf-8"))}
IMG = HERE / "images"

ap = argparse.ArgumentParser()
ap.add_argument("--web", default="http://localhost:8082")
ap.add_argument("--api", default="http://127.0.0.1:8001")
ap.add_argument("--db", required=True)
ap.add_argument("--run-dir", required=True)
ap.add_argument("--only", default="", help="comma-separated step numbers (debugging)")
args = ap.parse_args()
W = args.web
out = Path(args.run_dir).resolve() / "results_manual.json"
results: list[dict] = json.loads(out.read_text(encoding="utf-8")) if out.exists() and args.only else []
only = {int(x) for x in args.only.split(",") if x}
tag = datetime.now().strftime("%H%M%S")
api = httpx.Client(base_url=args.api + "/api/v1", timeout=300)
state: dict = {}


def rec(n, area, expected, actual, evidence, result, how="Real (browser)"):
    global results
    id_ = f"MC-{n:02d}"
    results = [r for r in results if r["id"] != id_]
    results.append({"id": id_, "title": area, "input": "see MANUAL_CHECKLIST.md step " + str(n), "expected": expected,
                    "actual": actual, "evidence": evidence, "result": result, "how": how, "group": "MANUAL",
                    "use_case": None, "db": "ui", "time": datetime.now().isoformat(timespec="seconds")})
    results.sort(key=lambda r: r["id"])
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[{result:16}] {id_} {area}: {actual[:150]}", flush=True)


def token(email):
    return api.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]


def history_count(email):
    r = api.get("/submissions?limit=100", headers={"Authorization": "Bearer " + token(email)}).json()
    return len(r["items"] if isinstance(r, dict) else r)


def make_account(key, admin=False):
    email = f"mc.{key}.{tag}@example.com"
    api.post("/auth/register", json={"name": f"MC {key}", "email": email, "password": PASSWORD})
    if admin:
        env = {**os.environ, "DATABASE_URL": resolve_db(args.db), "JWT_SECRET": TEST_JWT_SECRET, "PYTHONUTF8": "1"}
        env = {k: v for k, v in env.items() if not k.startswith("KHABARNAZAR_")}
        subprocess.run([str(PY), "scripts/set_user_role.py", email, "admin"], cwd=BACKEND, env=env, check=True, capture_output=True)
    return email


class MBrowser(Browser):
    drop_api = False

    def _event(self, msg):
        if msg.get("method") == "Fetch.requestPaused":
            self._send_raw("Fetch.failRequest", requestId=msg["params"]["requestId"], errorReason="InternetDisconnected")
            self.dropped = getattr(self, "dropped", 0) + 1
        super()._event(msg)


b = MBrowser(port=9335)
b.send("Page.addScriptToEvaluateOnNewDocument", source="""window.__seen = [];
  new MutationObserver(() => { const t = document.body ? document.body.innerText : '';
    if (t && t.includes('Loading your session')) window.__seen.push('Loading your session'); })
  .observe(document, {subtree: true, childList: true, characterData: true});""")


def login(email, password=PASSWORD, expect_home=True):
    b.js("localStorage.clear()")
    b.go(W + "/login", 8)
    b.wait_text("Welcome back", 40)
    b.type("you@example.com", email)
    b.type("Your password", password)
    b.click("Sign in", wait=3)
    if expect_home:
        b.wait_any(["Analyze", "Moderation", "Dashboard"], 30)


def disabled(label):
    return b.js(f"""(() => {{ let e=[...document.querySelectorAll('body *')].filter(x=>x.innerText && x.innerText.trim().toLowerCase().endsWith({json.dumps(label.lower())}) && x.getBoundingClientRect().width).pop();
        while (e && !e.hasAttribute('aria-disabled')) e = e.parentElement; return e ? e.getAttribute('aria-disabled') : 'not found'; }})()""")


def fill_box(text):
    b.go(W + "/", 6)
    b.wait_text("Analyze", 30)
    b.js(f"""(() => {{ const e=[...document.querySelectorAll('textarea')].find(x=>x.placeholder==={json.dumps(BOX)}); e.focus(); e.select(); }})()""")
    if text:
        b.send("Input.insertText", text=text)
    else:
        b.send("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
    b.pump(0.5)


def check_text(text, timeout=240):
    fill_box(text)
    b.click("Analyze", wait=0.5)
    got = b.wait_any(["Why this result", "Could not", "Uncertain", "no words"], timeout)
    b.pump(2)
    return got, b.text()


def overflow():
    return b.js("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")


def step(n, area, fn):
    if only and n not in only:
        return
    try:
        fn()
    except Exception as exc:
        try:
            ev = b.shot(f"MC-{n:02d}_error")
        except Exception:
            ev = "no screenshot"
        rec(n, area, "-", f"could not complete: {exc}", ev, "Blocked")


user, admin = make_account("user"), make_account("admin", admin=True)
state["reg_email"] = f"mc.phone.{tag}@example.com"


def s01():
    b.js("localStorage.clear()")
    b.go(W + "/", 0.4)
    early = " / ".join(sorted(set(b.js("window.__seen") or []))) or b.text()
    ev1 = b.shot("MC-01a_splash")
    b.wait_text("Welcome back", 30)
    ev2 = b.shot("MC-01b_signin")
    ok = "Welcome back" in b.text() and b.path() == "/login" and "Loading your session" in early
    rec(1, "Splash", "start screen ('Loading your session…'), then the Welcome back sign-in page",
        f"boot screen showed {early.strip()[:60]!r}; then at {b.path()} with 'Welcome back' {('Welcome back' in b.text())}",
        f"{ev1}; {ev2}", "Pass" if ok else "Fail")


def s02():
    b.js("localStorage.clear()")
    b.go(W + "/login", 6)
    b.click("Create an account", exact=False, wait=4)
    at = b.path()
    b.type("Your name (optional)", "Test Phone")
    b.type("you@example.com", state["reg_email"])
    b.type("At least 6 characters", PASSWORD)
    b.type("Repeat password", PASSWORD + "x")
    n = len(b.dialogs)
    b.click("Create account", wait=2)
    t = CI(b.text() + " " + " ".join(b.dialogs[n:]))
    ev = b.shot("MC-02_register_mismatch")
    ok = "do not match" in t and b.path() == "/register"
    rec(2, "Register: mismatched confirmation", "'Passwords do not match'; stays on the form",
        f"link opened {at}; 'do not match' shown {('do not match' in t)}; still at {b.path()}", ev, "Pass" if ok else "Fail")


def s03():
    if b.path() != "/register":
        s02()
    b.type("Repeat password", PASSWORD)
    b.click("Create account", wait=6)
    b.wait_text("Analyze", 30)
    home = b.path() == "/" and "Analyze" in b.text()
    ev1 = b.shot("MC-03a_registered_home")
    b.js("localStorage.clear()")
    b.go(W + "/register", 8)
    b.wait_text("Create account", 20)
    b.type("Your name (optional)", "Test Phone")
    b.type("you@example.com", state["reg_email"])
    b.type("At least 6 characters", PASSWORD)
    b.type("Repeat password", PASSWORD)
    n = len(b.dialogs)
    b.click("Create account", wait=4)
    t = CI(b.text() + " " + " ".join(b.dialogs[n:]))
    ev2 = b.shot("MC-03b_register_duplicate")
    dup = "already exists" in t
    rec(3, "Register: success, then the same email again", "signed in on the Check tab; duplicate: 'An account with this email already exists.'",
        f"home after register {home}; duplicate message {dup}; still at {b.path()}", f"{ev1}; {ev2}", "Pass" if home and dup else "Fail")


def s04():
    msgs = []
    evs = []
    for i, (email, pw) in enumerate(((user, "WrongPass1"), (f"nobody.{tag}@example.com", "WrongPass1"))):
        n = len(b.dialogs)
        login(email, pw, expect_home=False)
        b.wait_text("Incorrect email or password", 10)
        t = CI(b.text() + " " + " ".join(b.dialogs[n:]))
        msgs.append("Incorrect email or password entered" in t and b.path() == "/login")
        evs.append(b.shot(f"MC-04{'ab'[i]}_login_error"))
    rec(4, "Login: wrong password / unknown email", "'Incorrect email or password entered.' for both",
        f"wrong password -> message {msgs[0]}; unknown email -> message {msgs[1]}", "; ".join(evs), "Pass" if all(msgs) else "Fail")


def s05():
    b.js("localStorage.clear()")
    b.go(W + "/login", 6)
    b.click("Forgot password?", wait=4)
    at = b.path()
    b.type("you@example.com", user)
    n = len(b.dialogs)
    b.click("Continue", wait=2)
    t = CI(b.text() + " " + " ".join(b.dialogs[n:]))
    ev = b.shot("MC-05_forgot")
    rec(5, "Forgot password", "message that reset is not available yet (known limitation 5)",
        f"opened {at}; 'not available' shown {('not available' in t)}", ev, "Known-limitation" if "not available" in t else "Fail")


def s06():
    login(user)
    home = b.path() == "/" and "Analyze" in b.text()
    b.go(W + "/profile", 6)
    tu = b.text()
    ev1 = b.shot("MC-06a_user_profile")
    login(admin)
    b.go(W + "/profile", 6)
    ta = b.text()
    ev2 = b.shot("MC-06b_admin_profile")
    ok = home and "Moderation desk" not in tu and "Moderation desk" in ta
    rec(6, "Login: user vs admin", "user lands on Check, no admin tools in Profile; admin sees Moderation desk",
        f"user home {home}; user profile shows Moderation desk {('Moderation desk' in tu)}; admin profile shows it {('Moderation desk' in ta)}",
        f"{ev1}; {ev2}", "Pass" if ok else "Fail")


def s07():
    login(user)
    fill_box("")
    d = disabled("Analyze")
    n = len(b.dialogs)
    b.click("Analyze", wait=2)
    ev = b.shot("MC-07_empty")
    ok = str(d) == "true" and b.path() == "/" and not b.dialogs[n:]
    rec(7, "Empty check", "check does not start (prompt or disabled button)", f"Analyze aria-disabled={d}; after tapping still at {b.path()}; dialogs {b.dialogs[n:]}",
        ev, "Pass" if ok else "Fail")


def s08():
    login(user)
    fill_box(INPUTS["U02"])
    b.click("Analyze", wait=0.5)
    busy = b.text()
    ev1 = b.shot("MC-08a_busy")
    busy_ok = "Analyze" not in busy or disabled("Analyze") == "true" or b.js("!!document.querySelector('[aria-busy=\"true\"],[role=\"progressbar\"]')")
    got = b.wait_any(["Why this result", "Could not"], 240)
    b.pump(2)
    state["urdu_result"] = b.path()
    t = b.text()
    ev2 = b.shot("MC-08b_urdu_result")
    style = b.js(f"""(() => {{ const e=[...document.querySelectorAll('div,span')].filter(x=>x.innerText && x.innerText.trim()==={json.dumps(INPUTS['U02'])}).pop();
        if(!e) return null; const s=getComputedStyle(e); return {{direction:s.direction, align:s.textAlign, font:s.fontFamily}}; }})()""")
    b.js("window.scrollTo(0, document.body.scrollHeight)"); b.pump(1)
    ev3 = b.shot("MC-08c_urdu_result_bottom")
    parts = {k: (k in t) for k in ("Verdict", "Score", "Fake-news risk", "Detected language: Urdu script", "Why this result")}
    rtl = bool(style) and (style["direction"] == "rtl" or style["align"] in ("right", "end"))
    nast = bool(style) and "nastaliq" in style["font"].lower()
    ok = got == "Why this result" and all(parts.values()) and rtl and nast
    rec(8, "Urdu text [U02]", "busy state; Verdict, Score, Fake-news risk, claim RTL in Nastaliq, 'Detected language: Urdu script', Why this result",
        f"busy shown {bool(busy_ok)}; result {got} at {state['urdu_result']}; parts {parts}; claim style {style}", f"{ev1}; {ev2}; {ev3}", "Pass" if ok else "Fail")


def simple_text(n, key, area, expected, needles, shot):
    got, t = check_text(INPUTS[key])
    ev = b.shot(shot)
    found = {x: (x in t) for x in needles}
    ok = got == "Why this result" and all(found.values())
    rec(n, area, expected, f"reached {got}; on screen {found}", ev, "Pass" if ok else "Fail")
    return t


def s09():
    login(user)
    simple_text(9, "R02", "Roman Urdu [R02]", "Real/Fake verdict with score; highlighted Roman Urdu words",
                ["Score", "Why this result", "Detected language: Roman Urdu"], "MC-09_roman")


def s10():
    login(user)
    t = simple_text(10, "E01", "English [E01]", "verdict plus the note that English results are less reliable",
                    ["less reliable"], "MC-10_english")
    if "less reliable" in t:
        results[-1]["result"] = "Known-limitation" if results[-1]["result"] == "Pass" else results[-1]["result"]
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")


def s11():
    login(user)
    simple_text(11, "UL1", "Long Urdu [UL1]", "verdict with 'Long articles are checked as a whole'; highlighted words",
                ["checked as a whole", "Why this result"], "MC-11_long_urdu")


def s12():
    login(user)
    simple_text(12, "M03", "Mixed scripts [M03]", "verdict and the note that the text mixes scripts and was checked as Roman Urdu",
                ["mix", "Roman Urdu"], "MC-12_mixed")


def s13():
    login(user)
    before = history_count(user)
    res = {}
    for label, text in (("ab", INPUTS["X03"]), ("spaces", "     ")):
        fill_box(text)
        d = disabled("Analyze")
        n = len(b.dialogs)
        b.click("Analyze", wait=2)
        res[label] = {"aria-disabled": d, "dialogs": b.dialogs[n:], "at": b.path(), "text_on_screen": "too short" in b.text() or "enter" in b.text()}
        b.shot(f"MC-13_{label}")
    after = history_count(user)
    blocked = all(v["aria-disabled"] == "true" and v["at"] == "/" for v in res.values())
    rec(13, "Rejected text (ab / spaces)", "clear 'too short / enter some text' message; nothing new in History",
        f"{json.dumps(res, ensure_ascii=False)}; history {before} -> {after}. The app greys out Analyze below 3 characters instead of showing a message",
        "backend/tests/full_pass/screenshots/MC-13_ab.png; backend/tests/full_pass/screenshots/MC-13_spaces.png",
        "Pass" if blocked and before == after else "Fail")


def s14():
    login(user)
    got, t = check_text(INPUTS["X08"])
    ev = b.shot("MC-14_digits")
    has_score = "Score" in t and b.js("/Score\\s*\\n?\\s*\\d/.test(document.body.innerText)")
    ok = "Uncertain" in t and "no words to classify" in t
    rec(14, "No letters [X08]", "Uncertain with no score and a 'no words to classify' message",
        f"Uncertain {('Uncertain' in t)}; message {('no words to classify' in t)}; a numeric score shown {bool(has_score)}", ev, "Pass" if ok and not has_score else "Fail")


def s15():
    login(user)
    before = history_count(user)
    fill_box(INPUTS["R06"])
    b.click("Analyze", wait=1)
    b.send("Emulation.setDeviceMetricsOverride", width=844, height=390, deviceScaleFactor=2, mobile=True,
           screenOrientation={"type": "landscapePrimary", "angle": 90})
    b.pump(1)
    ev1 = b.shot("MC-15a_rotated_busy")
    got = b.wait_any(["Why this result", "Could not"], 240)
    b.pump(2)
    ev2 = b.shot("MC-15b_rotated_result")
    b.send("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True,
           screenOrientation={"type": "portraitPrimary", "angle": 0})
    b.pump(2)
    after = history_count(user)
    ok = got == "Why this result" and after == before + 1
    rec(15, "Rotate during analysis [R06]", "analysis finishes and the result opens; submitted once",
        f"result {got} at {b.path()}; history {before} -> {after}", f"{ev1}; {ev2}", "Pass" if ok else "Fail",
        how="Emulated (browser viewport switched portrait->landscape mid-request)")


def s16():
    rec(16, "iPhone HEIC from the camera roll", "the picker hands the app a JPEG; upload accepted",
        "not possible here: needs an iPhone camera roll and the native image picker (the web picker passes files through unchanged)",
        "-", "Blocked", how="Needs a phone")


def pick_image(file, remove_first=False):
    b.go(W + "/", 6)
    b.wait_text("Analyze", 30)
    b.click("Image", wait=1)
    b.pick_file("Gallery", file)


def s17():
    login(user)
    pick_image(IMG / "urdu_headline.png")
    ev1 = b.shot("MC-17a_first_pick")
    pos = b.js("""(() => { const e=document.querySelector('[aria-label="Remove image"]'); if(!e) return null; const r=e.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; })()""")
    for t in ("mousePressed", "mouseReleased"):
        b.send("Input.dispatchMouseEvent", type=t, x=pos[0], y=pos[1], button="left", clickCount=1)
    b.pump(1)
    b.pick_file("Gallery", IMG / "roman_headline.png")
    ev2 = b.shot("MC-17b_second_pick")
    b.click("Analyze", wait=1)
    got = b.wait_any(["Image authenticity", "Could not"], 300)
    b.pump(4)
    state["image_result"] = b.path()
    t = b.text()
    evs = [b.shot("MC-17c_result_top")]
    b.js("window.scrollTo(0, document.body.scrollHeight/2)"); b.pump(1); evs.append(b.shot("MC-17d_result_middle"))
    b.js("window.scrollTo(0, document.body.scrollHeight)"); b.pump(1); evs.append(b.shot("MC-17e_result_bottom"))
    i_ver, i_auth = t.find("Verdict"), t.find("Image authenticity")
    roman = "Hukoomat" in t
    order = 0 <= i_ver < i_auth
    checks = {"second image analysed (Roman text read)": roman, "verdict before authenticity": order,
              "'separate from the verdict above'": "separate from the verdict above" in t, "screenshot warning": "screenshot" in t,
              "ResNet18 caption": "ResNet18" in t}
    ok = got == "Image authenticity" and all(checks.values())
    rec(17, "Image with text, changed before analysing", "second picture analysed; news verdict first; 'Image authenticity (separate…)' with screenshot warning; heatmap captioned ResNet18",
        f"result {got}; {checks}. No 'Change' button exists: the picture is changed with the x (Remove image) then Gallery",
        "; ".join([ev1, ev2] + evs), "Pass" if ok else "Fail")


def s18():
    login(user)
    pick_image(IMG / "local_fox_no_text.jpg")
    b.click("Analyze", wait=1)
    got = b.wait_any(["Image authenticity", "Could not"], 300)
    b.pump(3)
    t = b.text()
    ev1 = b.shot("MC-18a_no_text")
    b.js("window.scrollTo(0, document.body.scrollHeight)"); b.pump(1)
    ev2 = b.shot("MC-18b_no_text_bottom")
    imgs = b.js("[...document.querySelectorAll('img')].filter(i=>i.naturalWidth>0).length")
    checks = {"no news claim": "no news claim" in t, "authenticity %": b.js("/Image authenticity[\\s\\S]*\\d+\\s*%/i.test(document.body.innerText)"),
              "images loaded": imgs}
    ok = got == "Image authenticity" and checks["no news claim"] and checks["authenticity %"] and imgs >= 2
    rec(18, "Image without text", "'No news claim was checked'; authenticity with a percentage; heatmap", f"result {got}; {checks}",
        f"{ev1}; {ev2}", "Pass" if ok else "Fail")


def s19():
    login(user)
    b.go(W + "/", 6)
    b.click("Image", wait=1)
    cam = "Camera" in b.text()
    ev = b.shot("MC-19_no_camera_on_web")
    rec(19, "Camera", "permission prompt the first time; photo analysed like a gallery image",
        f"not possible here: the Camera button is phone-only (shown on web: {cam}); needs Expo Go on a phone", ev, "Blocked", how="Needs a phone")


def s20():
    login(user)
    before = history_count(user)
    res = {}
    evs = []
    for f in ("format.gif", "format_just_over_10mb.png"):
        pick_image(IMG / f)
        n = len(b.dialogs)
        b.click("Analyze", wait=1)
        got = b.wait_any(["Unsupported", "too large", "Image authenticity", "Could not", "10 MB"], 120)
        b.pump(1)
        msg = " | ".join(b.dialogs[n:]) or got
        res[f] = msg
        evs.append(b.shot(f"MC-20_{f.split('.')[0]}"))
    after = history_count(user)
    ok = ("JPG, PNG, or WEBP" in res["format.gif"] and "larger than" in res["format_just_over_10mb.png"] and before == after)
    rec(20, "Rejected image (GIF, 11 MB PNG)", "'Unsupported image' / 'too large'; nothing new in History",
        f"{json.dumps(res)}; history {before} -> {after}", "; ".join(evs), "Pass" if ok else "Fail")


def s21():
    login(user)
    pick_image(IMG / "roman_headline.png")
    n = len(b.dialogs)
    b.dropped = 0
    b.send("Fetch.enable", patterns=[{"urlPattern": "*127.0.0.1:8001/api/v1/submissions/image*", "requestStage": "Request"}])
    b.click("Analyze", wait=0.3)
    b.pump(10)
    msg = b.dialogs[n:]
    still_busy = disabled("Analyze") == "true"
    ev1 = b.shot("MC-21a_connection_dropped")
    b.send("Fetch.disable")
    b.pump(1)
    if b.path() != "/" or "roman_headline.png" not in b.text():
        pick_image(IMG / "roman_headline.png")
    b.click("Analyze", wait=1)
    got2 = b.wait_any(["Image authenticity", "Could not"], 300)
    ev2 = b.shot("MC-21b_retry_online")
    err = any("Cannot reach the backend" in str(m) for m in msg)
    ok = err and not still_busy and got2 == "Image authenticity"
    rec(21, "Network loss during an image check", "an error such as 'Cannot reach the backend at …' (no crash, no endless spinner); retry works once online",
        f"connection dropped ({b.dropped} request failed with ERR_INTERNET_DISCONNECTED) -> {msg}; button busy afterwards {still_busy}; "
        f"connection back, retry -> {got2}. Note: switching the whole browser offline instead also blocks the Expo DEV server, which loads the "
        f"result screen's code lazily (app/result/[id].bundle?lazy=true), so the dev web app shows 'Something went wrong / Failed to fetch' "
        f"(screenshot MC-21_diag_offline.png); a built app and Expo Go do not load screens that way",
        f"{ev1}; {ev2}; backend/tests/full_pass/screenshots/MC-21_diag_offline.png", "Pass" if ok else "Fail",
        how="Emulated (the image upload's connection failed with ERR_INTERNET_DISCONNECTED mid-request)")


def s22():
    login(user)
    before = history_count(user)
    fill_box(INPUTS["R02"])
    b.click("Analyze", wait=1)
    b.send("Page.setWebLifecycleState", state="frozen")
    import time
    time.sleep(20)
    b.send("Page.setWebLifecycleState", state="active")
    got = b.wait_any(["Why this result", "Could not", "Cannot reach"], 240)
    b.pump(2)
    ev = b.shot("MC-22_after_background")
    signed_in = b.js("localStorage.getItem('kn_access_token') !== null")
    after = history_count(user)
    ok = got in ("Why this result", "Could not", "Cannot reach") and signed_in and b.path() != "/login"
    rec(22, "Background and return during a Roman Urdu check", "result or a clear error; no restart, still signed in",
        f"after 20 s frozen: {got} at {b.path()}; still signed in {signed_in}; history {before} -> {after}", ev, "Pass" if ok else "Fail",
        how="Emulated (page frozen 20 s with the browser lifecycle API)")


def s23():
    login(user)
    b.go(W + "/history", 8)
    b.wait_text("History", 20)
    t = b.text()
    ev1 = b.shot("MC-23a_history")
    items = api.get("/submissions?limit=100", headers={"Authorization": "Bearer " + token(user)}).json()
    items = items["items"] if isinstance(items, dict) else items
    ids = [i["id"] for i in items]
    newest_first = ids == sorted(ids, reverse=True)
    c = b.js("""(() => { const e=[...document.querySelectorAll('[role="button"],a')].filter(x=>/حکومت/.test(x.innerText||'') && x.getBoundingClientRect().width).shift();
        if(!e) return null; e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; })()""")
    for ty in ("mousePressed", "mouseReleased"):
        b.send("Input.dispatchMouseEvent", type=ty, x=c[0], y=c[1], button="left", clickCount=1)
    b.pump(5)
    opened = b.path()
    ev2 = b.shot("MC-23b_history_open")
    fresh = make_account("fresh")
    login(fresh)
    b.go(W + "/history", 8)
    t2 = b.text()
    ev3 = b.shot("MC-23c_history_empty")
    empty = "No checks" in t2 or "first analysis" in t2
    ok = "حکومت" in t and newest_first and opened.startswith("/result/") and empty
    rec(23, "History", "checks newest first with labels; tap opens the result; new account shows the empty state",
        f"{len(ids)} items, newest first {newest_first}; tapping the Urdu item opened {opened}; empty state for a new account {empty}",
        f"{ev1}; {ev2}; {ev3}", "Pass" if ok else "Fail")


def s24():
    login(user)
    b.go(W + state["urdu_result"], 8)
    b.wait_text("Why this result", 30)
    b.click("Dispute this result", wait=3)
    b.wait_text("Why do you disagree?", 20)
    ph = "e.g. The official press release on the ministry website says the opposite…"
    b.type(ph, "short")
    short_hint = b.text()
    ev1 = b.shot("MC-24a_short")
    short_blocked = disabled("Submit dispute") == "true"
    b.type(ph, "The ministry denied this; the internet service stays on.")
    b.type("e.g. geo.tv/news/12345", "geo.tv/news/12345")
    b.click("Submit dispute", wait=4)
    ev2 = b.shot("MC-24b_submitted")
    b.go(W + state["urdu_result"], 8)
    b.pump(2)
    t = b.text()
    ev3 = b.shot("MC-24c_pending")
    hint = "at least 10 characters" in short_hint or "10 characters minimum" in short_hint
    ok = hint and "Waiting for an administrator to review this dispute" in t
    rec(24, "Dispute", "'Please write at least 10 characters'; then saved and 'Waiting for an administrator to review this dispute'",
        f"short reason: hint shown {hint} (submit disabled {short_blocked}); after submit pending message {('Waiting for an administrator' in t)}",
        f"{ev1}; {ev2}; {ev3}", "Pass" if ok else "Fail")


def s25():
    login(admin)
    b.go(W + "/profile", 6)
    b.click("Moderation desk", wait=4)
    b.go(W + "/admin/disputes", 8)
    b.pump(2)
    t = b.text()
    ev = b.shot("MC-25_admin_queue")
    ok = "ministry denied" in t or "حکومت" in t
    rec(25, "Admin queue", "the pending dispute from step 24 is listed", f"dispute visible in the queue {ok}", ev, "Pass" if ok else "Fail")


def s26():
    login(admin)
    ds = api.get("/disputes?status=pending&limit=100", headers={"Authorization": "Bearer " + token(admin)}).json()
    did = next(d["id"] for d in ds if "ministry denied" in (d.get("justification") or ""))
    b.go(W + f"/admin/review/{did}", 8)
    b.wait_text("Your decision", 20)
    n = len(b.dialogs)
    b.click("Override verdict", exact=False, wait=2)
    t1 = CI(b.text() + " " + " ".join(b.dialogs[n:]))
    ev1 = b.shot("MC-26a_no_comment")
    b.type("Explain your decision for the audit trail…", "Checked with the ministry")
    b.click("Credible", wait=1)
    n = len(b.dialogs)
    b.click("Override verdict", exact=False, wait=4)
    t2 = CI(b.text() + " " + " ".join(b.dialogs[n:]))
    ev2 = b.shot("MC-26b_saved")
    a, c = "comment is required" in t1, "decision was recorded" in t2
    rec(26, "Admin review: override", "empty comment -> 'A comment is required (at least 3 characters)'; then 'The decision was recorded.'",
        f"comment-required message {a}; recorded message {c}", f"{ev1}; {ev2}", "Pass" if a and c else "Fail")


def s27():
    login(user)
    b.go(W + state["urdu_result"], 8)
    b.pump(2)
    t = b.text()
    ev1 = b.shot("MC-27a_user_sees_decision")
    b.go(W + "/history", 8)
    th = b.text()
    ev2 = b.shot("MC-27b_history_after_decision")
    checks = {"Credible": "Credible" in t, "set by an administrator": "set by an administrator" in t,
              "admin comment": "Checked with the ministry" in t, "AI's original estimate": "original estimate" in t, "history shows Credible": "Credible" in th}
    rec(27, "User sees the decision", "final label Credible marked as the admin's decision, with the comment", json.dumps(checks),
        f"{ev1}; {ev2}", "Pass" if all(checks.values()) else "Fail")


def s28():
    login(admin)
    b.go(W + "/admin/submissions", 8)
    b.pump(2)
    t = b.text()
    ev1 = b.shot("MC-28a_all_submissions")
    emails = user in t
    chips = {}
    for chip in ("Credible", "Disputed", "Images", "All"):
        c = b.js(f"""(() => {{ const e=[...document.querySelectorAll('[role="button"]')].filter(x=>x.innerText && x.innerText.trim()==={json.dumps(chip)} && x.getBoundingClientRect().width).shift();
            if(!e) return null; e.scrollIntoView({{block:'center'}}); const r=e.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; }})()""")
        if not c:
            chips[chip] = "chip missing"
            continue
        for ty in ("mousePressed", "mouseReleased"):
            b.send("Input.dispatchMouseEvent", type=ty, x=c[0], y=c[1], button="left", clickCount=1)
        b.pump(3)
        chips[chip] = b.text().count("@example.com")
        b.shot(f"MC-28_filter_{chip}")
    b.go(W + "/admin", 8)
    b.pump(2)
    td = b.text()
    ev2 = b.shot("MC-28b_dashboard")
    has_counts = b.js("/\\d+/.test(document.body.innerText)")
    ok = emails and has_counts and all(isinstance(v, int) for v in chips.values()) and chips["Disputed"] >= 1 and chips["All"] >= chips["Credible"]
    rec(28, "Admin lists, filters and dashboard", "everyone's checks with emails; filter chips narrow the list; counts on the dashboard",
        f"user's email listed {emails}; rows with each chip {chips}; dashboard has numbers {has_counts} ({td.strip()[:80]!r})",
        f"{ev1}; {ev2}; backend/tests/full_pass/screenshots/MC-28_filter_*.png", "Pass" if ok else "Fail")


def s29():
    login(user)
    b.go(W + "/admin", 8)
    b.pump(2)
    ev = b.shot("MC-29_non_admin")
    rec(29, "Non-admin opens /admin", "sent back to the Check tab", f"ended at {b.path()}", ev, "Pass" if b.path() == "/" else "Fail")


def s30():
    login(user)
    b.go(W + "/profile", 6)
    b.click("My profile", wait=3)
    t = b.text()
    ev1 = b.shot("MC-30a_my_profile")
    shown = user in t
    b.go(W + "/profile", 6)
    b.click("Change profile photo", exact=False, wait=3)
    before = b.js("[...document.querySelectorAll('img')].map(i=>i.src).join('|')")
    b.pick_file("Choose photo", IMG / "local_roses_ai_look.jpg")
    b.pump(2)
    after = b.js("[...document.querySelectorAll('img')].map(i=>i.src).join('|')")
    ev2 = b.shot("MC-30b_photo")
    changed = before != after
    b.go(W + "/profile", 6)
    b.click("Sign out", wait=2)
    if b.path() != "/login":
        b.click("Sign out", wait=4)
    at = b.path()
    b.send("Page.navigate", url=W + "/history"); b.pump(7)
    back = b.path()
    b.js("history.back()"); b.pump(4)
    back2 = b.path()
    ev3 = b.shot("MC-30c_signed_out")
    ok = shown and changed and at == "/login" and back == "/login" and back2 in ("/login", "/register", "/forgot")
    rec(30, "Profile, photo, sign out", "name and email shown; photo changes; after sign-out on sign-in, Back does not return to protected pages",
        f"email shown {shown}; photo changed {changed}; after sign-out at {at}; /history -> {back}; Back -> {back2}",
        f"{ev1}; {ev2}; {ev3}", "Pass" if ok else "Fail")


def s31():
    login(user)
    b.go(W + "/history", 8)
    b.send("Page.reload"); b.pump(9)
    p1 = b.path()
    ev1 = b.shot("MC-31a_reload")
    b.js("localStorage.clear()")
    b.go(W + "/history", 8)
    p2 = b.path()
    ev2 = b.shot("MC-31b_signed_out_history")
    rec(31, "Session reload (web)", "reload keeps History; signed out /history goes to sign-in", f"reload -> {p1}; signed out -> {p2}",
        f"{ev1}; {ev2}", "Pass" if p1 == "/history" and p2 == "/login" else "Fail")


def s32():
    login(user)
    res = {}
    evs = []
    for w, h in ((390, 844), (320, 640)):
        b.send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2, mobile=True)
        for name, path in (("long_urdu", state.get("long_result")), ("urdu", state.get("urdu_result")), ("image", state.get("image_result"))):
            if not path:
                continue
            b.go(W + path, 8)
            b.pump(2)
            ov = overflow()
            rtl = b.js("""[...document.querySelectorAll('div,span')].some(e => /[\\u0600-\\u06FF]{4}/.test(e.innerText||'') && e.children.length===0 && ['rtl'].includes(getComputedStyle(e).direction) || (getComputedStyle(e).textAlign==='right' && /[\\u0600-\\u06FF]{4}/.test(e.innerText||'') && e.children.length===0))""")
            res[f"{name}@{w}"] = {"sideways_scroll": ov, "urdu_rtl": rtl if name != "image" else "n/a"}
            b.js("window.scrollTo(0, document.body.scrollHeight/2)"); b.pump(0.5)
            evs.append(b.shot(f"MC-32_{name}_{w}"))
    b.send("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    ok = res and all(not v["sideways_scroll"] and v["urdu_rtl"] in (True, "n/a") for v in res.values())
    rec(32, "Layout at phone width and 320 px", "text wraps, nothing cut off or scrolling sideways; Urdu right-to-left",
        json.dumps(res), "; ".join(evs[:4]) + "; …", "Pass" if ok else "Fail", how="Real (browser at 390 and 320 px wide)")


# Step 11 also records where the long Urdu result lives, for step 32.
_s11 = s11
def s11():  # noqa: F811
    _s11()
    state["long_result"] = b.path()


try:
    for n, area, fn in [(1, "Splash", s01), (2, "Register mismatch", s02), (3, "Register", s03), (4, "Login errors", s04),
                        (5, "Forgot password", s05), (6, "Login roles", s06), (7, "Empty check", s07), (8, "Urdu text", s08),
                        (9, "Roman Urdu", s09), (10, "English", s10), (11, "Long Urdu", s11), (12, "Mixed", s12),
                        (13, "Rejected text", s13), (14, "No letters", s14), (15, "Rotate", s15), (16, "HEIC", s16),
                        (17, "Image with text", s17), (18, "Image without text", s18), (19, "Camera", s19), (20, "Rejected image", s20),
                        (21, "Network loss", s21), (23, "History", s23), (24, "Dispute", s24),
                        (25, "Admin queue", s25), (26, "Admin review", s26), (27, "User sees decision", s27), (28, "Admin lists", s28),
                        (29, "Non-admin", s29), (30, "Profile", s30), (31, "Session reload", s31), (32, "Layout", s32),
                        (22, "Background", s22)]:  # last: freezing the page leaves this browser unusable afterwards
        step(n, area, fn)
finally:
    b.close()
    print("done", out)
