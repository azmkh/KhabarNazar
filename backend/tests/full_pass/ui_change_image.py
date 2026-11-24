"""TC-UI-10b: pick an image, remove it with the x button, pick another, analyse; the second is analysed.

    python tests/full_pass/ui_change_image.py --run-dir RUN   (Expo web on 8082, backend on 8001; from PowerShell)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui_pass import HERE, PASSWORD, Browser  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--run-dir", required=True)
ap.add_argument("--web", default="http://localhost:8082")
ap.add_argument("--api", default="http://127.0.0.1:8001")
args = ap.parse_args()
out = Path(args.run_dir) / "results_ui.json"
results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
email = f"ui.change.{datetime.now():%H%M%S}@example.com"
httpx.post(args.api + "/api/v1/auth/register", json={"name": "UI Change", "email": email, "password": PASSWORD})

b = Browser(port=9334)
try:
    b.go(args.web + "/login", 8)
    b.wait_text("Welcome back", 40)
    b.type("you@example.com", email)
    b.type("Your password", PASSWORD)
    b.click("Sign in", wait=4)
    b.wait_text("Analyze", 30)
    b.click("Image", wait=1)
    b.pick_file("Gallery", HERE / "images" / "roman_headline.png")
    ev1 = b.shot("UI-10b1_first_pick")
    pos = b.js("""(() => { const e=document.querySelector('[aria-label="Remove image"]'); if(!e) return null; const r=e.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; })()""")
    for t in ("mousePressed", "mouseReleased"):
        b.send("Input.dispatchMouseEvent", type=t, x=pos[0], y=pos[1], button="left", clickCount=1)
    b.pump(1)
    removed = b.js("!document.querySelector('[aria-label=\"Remove image\"]')")
    b.pick_file("Gallery", HERE / "images" / "urdu_headline.png")
    ev2 = b.shot("UI-10b2_second_pick")
    b.click("Analyze", wait=1)
    got = b.wait_any(["Image authenticity", "Could not"], 300)
    b.pump(3)
    t = b.text()
    ev3 = b.shot("UI-10b3_result")
    urdu_ocr = bool(re.search(r"انٹرنیٹ|حکومت|اعلان", t))
    roman_ocr = "Hukoomat ne mulk" in t
    ok = removed and got == "Image authenticity" and urdu_ocr and not roman_ocr
    results = [r for r in results if r["id"] != "TC-UI-10b"]
    results.append({"id": "TC-UI-10b", "title": "Change the picked image (x, then Gallery again) before analysing", "input": "roman_headline.png, removed, then urdu_headline.png",
                    "expected": "the preview clears; the second picture (Urdu) is the one analysed", "actual": f"preview cleared {removed}; result reached {got}; "
                    f"result shows the Urdu headline text {urdu_ocr}; shows the Roman one {roman_ocr}", "evidence": f"{ev1}; {ev2}; {ev3}",
                    "result": "Pass" if ok else "Fail", "how": "Real (browser)", "group": "UI", "use_case": "UC-4 Submit Image", "db": "ui",
                    "time": datetime.now().isoformat(timespec="seconds")})
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(results[-1]["result"], results[-1]["actual"])
finally:
    b.close()
