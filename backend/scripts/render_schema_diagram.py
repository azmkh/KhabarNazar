"""Render backend/docs/database-schema.png from the Mermaid diagram in backend/docs/DATABASE.md.

Run after scripts/describe_database.py has regenerated DATABASE.md (for example after a new
migration), from backend/:

    .venv/Scripts/python.exe scripts/render_schema_diagram.py

It needs Microsoft Edge or Google Chrome (used headless) and an internet connection, because
Mermaid is loaded from the jsDelivr CDN at a pinned version. Nothing else is installed.
Use --browser to point at a browser executable that is not in a standard location.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
MARKDOWN = DOCS / "DATABASE.md"
OUTPUT = DOCS / "database-schema.png"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
WIDTH, HEIGHT, SCALE = 1880, 2400, 1.12  # about 2106 pixels wide, like the earlier image; height is trimmed

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser(explicit: str | None) -> str:
    candidates = [explicit] if explicit else BROWSERS + [
        shutil.which(name) for name in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome")
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    sys.exit("No Edge or Chrome found; pass --browser <path to the browser executable>.")


def read_markdown() -> tuple[str, str]:
    text = MARKDOWN.read_text(encoding="utf-8")
    diagram = re.search(r"```mermaid\n(.*?)```", text, re.S)
    revision = re.search(r"Migration revision \| `([0-9a-f]+)`", text)
    if not diagram or not revision:
        sys.exit("DATABASE.md has no Mermaid diagram or migration revision; run scripts/describe_database.py first.")
    return diagram.group(1), revision.group(1)


def page(diagram: str, revision: str) -> str:
    today = dt.date.today().isoformat()
    legend = [
        ("||--o{", "one to many"), ("||--o|", "one to zero-or-one"),
        ("PK", "primary key"), ("FK", "foreign key"), ("UK", "unique"),
    ]
    legend_html = "".join(f"<span><b>{html.escape(code)}</b> {label}</span>" for code, label in legend)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>KhabarNazar database schema</title>
<style>
  body {{ margin: 0; background: #fff; font-family: "Segoe UI", system-ui, sans-serif; color: #1f1f2e; }}
  main {{ width: {WIDTH - 140}px; padding: 60px 70px 40px; }}
  h1 {{ margin: 0; font-size: 44px; display: flex; align-items: center; gap: 16px; }}
  h1::before {{ content: ""; width: 20px; height: 20px; border-radius: 5px; background: linear-gradient(135deg, #6d28d9, #9333ea); }}
  p {{ margin: 10px 0 30px; color: #555; font-size: 22px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 36px; font-size: 22px; color: #555; margin-top: 30px; }}
  .legend b {{ font-family: Consolas, monospace; color: #1f1f2e; }}
  pre.mermaid {{ margin: 0; }}
  pre.mermaid svg {{ width: 100% !important; max-width: none !important; height: auto; }}
</style></head>
<body><main>
<h1>KhabarNazar database schema</h1>
<p>PostgreSQL · migration revision {revision} · generated {today} from backend/docs/DATABASE.md</p>
<pre class="mermaid">{html.escape(diagram)}</pre>
<div class="legend">{legend_html}<span>All links ON DELETE CASCADE · times are TIMESTAMPTZ (UTC)</span></div>
</main>
<script src="{MERMAID_URL}"></script>
<script>mermaid.initialize({{ startOnLoad: true, theme: "default", themeVariables: {{ lineColor: "#7b5cd6" }},
  er: {{ useMaxWidth: true }} }});</script>
</body></html>
"""


def trim_bottom(source: Path, destination: Path, margin: int = 70) -> None:
    """Cut the empty white space below the legend (the browser window is taller than the page)."""
    from PIL import Image, ImageChops

    with Image.open(source) as img:
        rgb = img.convert("RGB")
        box = ImageChops.difference(rgb, Image.new("RGB", rgb.size, "white")).getbbox()
        bottom = min(rgb.height, box[3] + margin) if box else rgb.height
        rgb.crop((0, 0, rgb.width, bottom)).save(destination, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", help="path to Edge or Chrome")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    browser = find_browser(args.browser)
    diagram, revision = read_markdown()
    with tempfile.TemporaryDirectory(prefix="khabarnazar-schema-") as folder:
        source = Path(folder) / "schema.html"
        source.write_text(page(diagram, revision), encoding="utf-8")
        shot = Path(folder) / "schema.png"
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={folder}",
             f"--window-size={WIDTH},{HEIGHT}", f"--force-device-scale-factor={SCALE}",
             "--virtual-time-budget=15000", f"--screenshot={shot}", source.as_uri()],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )
        if not shot.is_file() or shot.stat().st_size < 10_000:
            sys.exit("The browser did not produce the diagram (is the internet connection working?).")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        trim_bottom(shot, args.output)
    print(f"Wrote {args.output} (revision {revision}).")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
